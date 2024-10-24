#!/usr/bin/env python3

"""
author: mwiget
coauthor: cklewar
"""

import argparse
import json
import logging
import os
import concurrent.futures
import threading
import time

import requests
import sys
from pathlib import Path
from requests import Response

# Configure the logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

QUERY_STRING_LB_HTTP = "/http_loadbalancers/"
QUERY_STRING_LB_TCP = "/tcp_loadbalancers/"
URI_F5XC_NAMESPACE = "/web/namespaces"
URI_F5XC_SITES = "/config/namespaces/system/sites"
URI_F5XC_LOAD_BALANCER = "/config/namespaces/{namespace}/{lb_type}"
URI_F5XC_ORIGIN_POOLS = "/config/namespaces/{namespace}/origin_pools"
URI_F5XC_PROXIES = "/config/namespaces/{namespace}/proxys"
F5XC_SITE_TYPES = ["site", "virtual_site"]
F5XC_LOAD_BALANCER_TYPES = ["http_loadbalancers", "tcp_loadbalancers"]
F5XC_ORIGIN_SERVER_TYPES = ['private_ip', 'k8s_service', 'consul_service', 'private_name']


class Api(object):
    """
    Represents the query API.

    Attributes
    ----------
    api_url : str
        F5XC API URL
    api_token : str
        F5XC API token
    session: request.Session
        http session
    workers: int
       maximum number of workers

    Methods
    -------
    build_url(uri=None)
        builds api url based on uri
    write_json_file(name=None)
        writes data to json file
    run()
        run the queries and build ds
    process_load_balancers()
        get and process load balancers
    process_proxies()
        get and process proxies
    process_origin_pools()
        get and process origin pools
    """

    def __init__(self, api_url: str = None, api_token: str = None, namespace: str = None, workers: int = 10):
        """
        Initialize API object. Stores session state and allows to run data processing methods.

        :param api_url: F5XC API URL
        :param api_token: F5XC API token
        :param namespace: F5XC namespace
        :param workers: Maximum number of workers for concurrent processing
        """

        self.data = {key: dict() for key in F5XC_SITE_TYPES}
        self.lock = threading.Lock()
        self.api_url = api_url
        self.api_token = api_token
        self.workers = workers
        self.session = requests.Session()
        self.session.headers.update({"content-type": "application/json", "Authorization": f"APIToken {api_token}"})

        logger.info(f"API URL: {self.api_url} -- Processing Namespace: {namespace if namespace else 'ALL'}")

        if not namespace:
            # get list of all namespaces
            response = self.get(self.build_url(URI_F5XC_NAMESPACE))

            if response:
                logger.debug(json.dumps(response.json(), indent=2))
                json_items = response.json()
                self.data['namespaces'] = [item['name'] for item in json_items['items']]
                logger.info(f"Available namespaces: {self.data['namespaces']}")
            else:
                sys.exit(1)

        else:
            # check api url and validate given namespace
            response = self.get(self.build_url(f"{URI_F5XC_NAMESPACE}/{namespace}"))

            if response:
                logger.debug(json.dumps(response.json(), indent=2))
                self.data['namespaces'] = [namespace]
            else:
                sys.exit(1)

    def get(self, url: str = None) -> Response | bool:
        """
        Run HTTP GET on a given url
        :param url: Actual URL to run GET request on
        :return: requests.Response
        """
        r = self.session.get(url)

        if 200 != r.status_code:
            logger.error("get failed for {} with {}".format(url, r.status_code))
            logger.info(f"get failed for  {url} with {r.status_code}")
            return False

        return r if r else False

    def build_url(self, uri: str = None) -> str:
        """
        Build url from api url + resource uri
        :param uri: the resource uri
        :return: url string
        """
        return "{}{}".format(self.api_url, uri)

    def write_json_file(self, name: str = None):
        """
        Write json to file
        :param name: The file name to write json into
        :return:
        """
        if name not in ['stdout', '-', '']:
            try:
                with open(name, 'w') as fd:
                    fd.write(json.dumps(self.data, indent=2))
                    logger.info(f"{len(self.data['site'])} sites and {len(self.data['virtual_site'])} virtual sites written to {name}")
            except OSError as e:
                logger.info(f"Writing file {name} failed with error: {e}")
        else:
            logger.info(json.dumps(self.data, indent=2))

    def run(self) -> dict:
        """
        Run functions to process data
            - process_loadbalancer for each namespace and load balancer type
            - process_proxies for each namespace
            - process_origin_pools for each namespace
            - process site labels only if referenced by a load balancer/ origin pool / proxy
        :return:
        """

        lb_urls = list()
        proxy_urls = list()
        origin_pool_urls = list()
        lbs = list()
        proxies = list()
        origin_pools = list()

        for namespace in self.data["namespaces"]:
            proxy_urls.append(self.build_url(URI_F5XC_PROXIES.format(namespace=namespace)))
            origin_pool_urls.append(self.build_url(URI_F5XC_ORIGIN_POOLS.format(namespace=namespace)))

            for lb_type in F5XC_LOAD_BALANCER_TYPES:
                lb_urls.append(self.build_url(URI_F5XC_LOAD_BALANCER.format(namespace=namespace, lb_type=lb_type)))

        logger.debug("LB_URLS: %s", lb_urls)
        logger.debug("PROXY_URLS: %s", proxy_urls)
        logger.debug("ORIGIN_POOL_URLS: %s", origin_pool_urls)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            logger.info("Prepare load balancer query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in lb_urls}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    data = future.result()
                except Exception as exc:
                    logger.info('%r generated an exception: %s' % (_data, exc))
                else:
                    lbs.append({future_to_ds[future]: data.json()["items"]}) if data and data.json()["items"] else None

        self.process_load_balancers(lbs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            logger.info("Prepare proxies query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in proxy_urls}
            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    data = future.result()
                except Exception as exc:
                    logger.info('%r generated an exception: %s' % (_data, exc))
                else:
                    proxies.append({future_to_ds[future]: data.json()["items"]}) if data and data.json()["items"] else None

        self.process_proxies(proxies)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            logger.info("Prepare origin pools query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in origin_pool_urls}
            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    data = future.result()
                except Exception as exc:
                    logger.info('%r generated an exception: %s' % (_data, exc))
                else:
                    origin_pools.append({future_to_ds[future]: data.json()["items"]}) if data and data.json()["items"] else None

        self.process_origin_pools(origin_pools)
        self.process_sites()

        return self.data

    def process_load_balancers(self, data: list = None) -> dict:
        """
        Add load balancer to site if load balancer refers to a site. Obtains specific load balancer by name.
        :param data: url to load balancer mapping for all load balancer in given namespace
        :return structure with load balancer information being added
        """

        urls = list()

        for item in data:
            for url, lbs in item.items():
                for lb in lbs:
                    _url = "{}/{}".format(url, lb['name'])
                    urls.append(_url)

        logger.debug(f"{self.process_load_balancers.__name__} url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    logger.info(f"{self.process_load_balancers.__name__} get item {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    logger.info('%s: %r generated an exception: %s' % (self.process_load_balancers.__name__, _data, exc))
                else:
                    logger.info(f"{self.process_load_balancers.__name__} got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        logger.debug(json.dumps(r, indent=2))
                        if 'advertise_custom' in r['spec'] and 'advertise_where' in r['spec']['advertise_custom']:
                            for index, site_info in enumerate(r['spec']['advertise_custom']['advertise_where']):
                                if 'site' in site_info:
                                    for site_type in site_info['site'].keys():
                                        if site_type in F5XC_SITE_TYPES:
                                            try:
                                                lb_name = r["metadata"]["name"]
                                                site_name = site_info['site'][site_type]['name']
                                                namespace = r["metadata"]["namespace"]
                                                if site_name not in self.data[site_type].keys():
                                                    self.data[site_type][site_name] = dict()
                                                if 'namespaces' not in self.data[site_type][site_name].keys():
                                                    self.data[site_type][site_name]['namespaces'] = dict()
                                                if namespace not in self.data[site_type][site_name]['namespaces'].keys():
                                                    self.data[site_type][site_name]['namespaces'][namespace] = dict()
                                                if "loadbalancer" not in self.data[site_type][site_name]['namespaces'][namespace].keys():
                                                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"] = dict()
                                                if QUERY_STRING_LB_TCP in future_to_ds[future]:
                                                    if "tcp" not in self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"].keys():
                                                        self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["tcp"] = dict()
                                                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["tcp"][lb_name] = None
                                                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["tcp"][lb_name] = r['system_metadata']
                                                if QUERY_STRING_LB_HTTP in future_to_ds[future]:
                                                    if "http" not in self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"].keys():
                                                        self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["http"] = dict()
                                                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["http"][lb_name] = None
                                                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["http"][lb_name] = r['system_metadata']

                                                logger.info(f"{self.process_load_balancers.__name__} add data: [namespace: {namespace} loadbalancer: {lb_name} site_type: {site_type} site_name: {site_name}]")
                                            except Exception as e:
                                                logger.info("lb_name:", lb_name)
                                                logger.info("site_type:", site_type)
                                                logger.info("site_name:", site_name)
                                                logger.info("namespace:", r["metadata"]["namespace"])
                                                logger.info("system_metadata:", r['system_metadata'])
                                                logger.info("Exception:", e)

        return self.data

    def process_proxies(self, data: list = None) -> dict:
        """
        Add proxies to site if proxy refers to a site. Obtains specific proxy by name.
        :param data: url to proxy mapping for all proxies in given namespace
        :return structure with proxies information being added
        """

        urls = list()

        for item in data:
            for url, proxies in item.items():
                for proxy in proxies:
                    _url = "{}/{}".format(url, proxy['name'])
                    urls.append(_url)

        logger.debug(f"{self.process_proxies.__name__} url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    logger.info(f"{self.process_proxies.__name__} get item {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    logger.info('%s: %r generated an exception: %s' % (self.process_proxies.__name__, _data, exc))
                else:
                    logger.info(f"{self.process_proxies.__name__} got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        logger.debug(json.dumps(r, indent=2))
                        site_virtual_sites = r['spec'].get('site_virtual_sites', {})
                        advertise_where = site_virtual_sites.get('advertise_where', [])

                        for site_info in advertise_where:
                            site = site_info.get('site', {})
                            for site_type in F5XC_SITE_TYPES:
                                if site_type in site:
                                    site_name = site[site_type].get('name')
                                    if site_name:
                                        try:
                                            proxy_name = r["metadata"]["name"]
                                            site_name = site_info['site'][site_type]['name']
                                            namespace = r["metadata"]["namespace"]
                                            if site_name not in self.data[site_type].keys():
                                                self.data[site_type][site_name] = dict()
                                                self.data[site_type][site_name]['namespaces'] = dict()
                                            if namespace not in self.data[site_type][site_name]['namespaces'].keys():
                                                self.data[site_type][site_name]['namespaces'][namespace] = dict()
                                            if "proxys" not in self.data[site_type][site_name]['namespaces'][namespace].keys():
                                                self.data[site_type][site_name]['namespaces'][namespace]["proxys"] = dict()
                                            self.data[site_type][site_name]['namespaces'][namespace]["proxys"][proxy_name] = None
                                            self.data[site_type][site_name]['namespaces'][namespace]['proxys'][proxy_name] = r['system_metadata']
                                            logger.info(f"{self.process_proxies.__name__} add data: [namespace: {namespace} proxy: {proxy_name} site_type: {site_type} site_name: {site_name}]")
                                        except Exception as e:
                                            logger.info("lb_name:", proxy_name)
                                            logger.info("site_type:", site_type)
                                            logger.info("site_name:", site_name)
                                            logger.info("namespace:", r["metadata"]["namespace"])
                                            logger.info("system_metadata:", r['system_metadata'])
                                            logger.info("Exception:", e)

        return self.data

    def process_origin_pools(self, data: list = None) -> dict:
        """
        Add origin pools to site if origin pools refers to a site. Obtains specific origin pool by name.
        :param data: url to origin pools mapping for all origin pools in given namespace
        :return structure with origin pool information being added
        """

        urls = list()

        for item in data:
            for url, origin_pools in item.items():
                for origin_pool in origin_pools:
                    _url = "{}/{}".format(url, origin_pool['name'])
                    urls.append(_url)

        logger.debug(f"{self.process_origin_pools.__name__} url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    logger.info(f"{self.process_origin_pools.__name__} get item {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    logger.info('%s: %r generated an exception: %s' % (self.process_origin_pools.__name__, _data, exc))
                else:
                    logger.info(f"{self.process_origin_pools.__name__} got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        logger.debug(json.dumps(r, indent=2))
                        origin_servers = r['spec'].get('origin_servers', [])

                        for origin_server in origin_servers:
                            for key in F5XC_ORIGIN_SERVER_TYPES:
                                site_locator = origin_server.get(key, {}).get('site_locator', {})

                                for site_type, site_data in site_locator.items():
                                    site_name = site_data.get('name')

                                    if site_name:
                                        try:
                                            origin_pool_name = r["metadata"]["name"]
                                            namespace = r["metadata"]["namespace"]
                                            if site_name not in self.data[site_type].keys():
                                                self.data[site_type][site_name] = dict()
                                                self.data[site_type][site_name]['namespaces'] = dict()
                                            if namespace not in self.data[site_type][site_name]['namespaces'].keys():
                                                self.data[site_type][site_name]['namespaces'][namespace] = dict()
                                            if "origin_pools" not in self.data[site_type][site_name]['namespaces'][namespace].keys():
                                                self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"] = dict()
                                            self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"][origin_pool_name] = None
                                            self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"][origin_pool_name] = r['system_metadata']
                                            logger.info(f"{self.process_origin_pools.__name__} add data: [namespace: {namespace} proxy: {origin_pool_name} site_type: {site_type} site_name: {site_name}]")
                                        except Exception as e:
                                            logger.info("site_type:", site_type)
                                            logger.info("site_name:", site_name)
                                            logger.info("namespace:", r["metadata"]["namespace"])
                                            logger.info("system_metadata:", r['system_metadata'])
                                            logger.info("origin_pool_name:", origin_pool_name)
                                            logger.info("Exception:", e)
        return self.data

    def process_sites(self) -> dict:
        """
        Get list of sites and process labels. Only add labels to sites that are referenced by a LB/origin_pool/proxys object.
        Store the sites with only origin pools and without origin pools or load balancers.
        Check if the site has origin pools only (and no load balancer).
        :return: structure with label information being added
        """

        logger.info(f"{self.process_sites.__name__} get all sites from {self.build_url(URI_F5XC_SITES)}")
        _sites = self.get(self.build_url(URI_F5XC_SITES))

        if _sites:
            logger.debug(json.dumps(_sites.json(), indent=2))
            sites = _sites.json()

            for site in sites['items']:
                if site['name'] in self.data['site']:
                    logger.info(f"{self.process_sites.__name__} add label information to site {site['name']}")
                    self.data['site'][site['name']]['labels'] = site['labels']

            sites_with_origin_pools_only = []

            for site_name, site_data in self.data['site'].items():
                for n_name, n_data in site_data['namespaces'].items():
                    # Check if the site has origin pools only
                    if len(n_data.keys()) == 1 and 'origin_pools' in n_data.keys():
                        sites_with_origin_pools_only.append(site_name)

            self.data["sites_with_origin_pools_only"] = sites_with_origin_pools_only
            logger.info(f"{self.process_sites.__name__} <{len(sites_with_origin_pools_only)}> sites with origin pools only: {sites_with_origin_pools_only}")

            self.data["orphaned_sites"] = [k for k, v in self.data['site'].items() if 'labels' not in v.keys()]
            logger.info(f"{self.process_sites.__name__} <{len(self.data["orphaned_sites"])}> sites without labels (orphaned): {self.data["orphaned_sites"]}")

            return self.data


def main():
    logger.info(f"Application {os.path.basename(__file__)} started...")

    # Create the parser
    parser = argparse.ArgumentParser(description="Get F5 XC Sites command line arguments")

    # Add arguments
    parser.add_argument('-n', '--namespace', type=str, help='Namespace (not setting this option will process all namespaces)', required=False, default='')
    parser.add_argument('-a', '--apiurl', type=str, help='F5 XC API URL', required=False, default='')
    parser.add_argument('-t', '--token', type=str, help='F5 XC API Token', required=False, default='')
    parser.add_argument('-f', '--file', type=str, help='write site list to file', required=False, default=Path(__file__).stem + '.json')
    parser.add_argument('-w', '--workers', type=int, help='maximum number of worker for concurrent processing', required=False, default=10)
    parser.add_argument('--log-level', type=str, help='set log level to INFO or DEBUG', required=False, default="INFO")
    parser.add_argument('--log-stdout', help='write log info to stdout', action='store_true')
    parser.add_argument('--log-file', help='write log info to file', action='store_true')

    # Parse the arguments
    args = parser.parse_args()

    if os.environ.get('GET-SITES-LOG-LEVEL'):
        level = getattr(logging, os.environ.get('GET-SITES-LOG-LEVEL').upper(), None)
    else:
        level = getattr(logging, args.log_level.upper(), None)

    if not isinstance(level, int):
        raise ValueError('Invalid log level: %s' % os.environ.get('GET-SITES-LOG-LEVEL').upper())

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    if args.log_stdout:
        ch = logging.StreamHandler()
        ch.setLevel(level=level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    if args.log_file:
        fh = logging.FileHandler(args.log_file, "w", encoding="utf-8") if args.file is None else logging.FileHandler(Path(__file__).stem + '.log', "w", encoding="utf-8")
        fh.setLevel(level=level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    api_url = args.apiurl if args.apiurl else os.environ.get('f5xc_api_url')
    api_token = args.token if args.token else os.environ.get('f5xc_api_token')

    if not api_url or not api_token:
        parser.print_help()
        sys.exit(1)

    logger.info(f"Application {os.path.basename(__file__)} started...")
    start_time = time.perf_counter()
    q = Api(api_url=api_url, api_token=api_token, namespace=args.namespace, workers=args.workers)
    q.run()
    q.write_json_file(args.file)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f'Query time: {int(elapsed_time)} seconds with {args.workers} workers')
    logger.info(f"Application {os.path.basename(__file__)} finished")


if __name__ == '__main__':
    main()
