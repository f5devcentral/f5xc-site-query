#!/usr/bin/env python3

import argparse
import json
import logging
import os
import concurrent.futures

import requests
import sys
from pathlib import Path
from collections import defaultdict, namedtuple

from requests import Response, Session, session

# Configure the logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).stem + '.log', "w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

MAX_WORKERS = 10
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
        namespaces : str
            F5XC namespace
        session: request.Session
            http session

        Methods
        -------
        build_url(uri=None)
            builds api url based on uri
        write_json_file(name=None)
            writes data to json file
        read_json_file(name=None)
            read data from json file
        run()
            run the queries and build ds
        process_load_balancers()
            get and process load balancers
        process_proxies()
            get and process proxies
        process_origin_pools()
            get and process origin pools
        """

    def __init__(self, api_url: str = None, api_token: str = None, namespace: str = None):
        """
        Initialize API object

        :param api_url: F5XC API URL
        :param api_token: F5XC API token
        :param namespace: F5XC namespace
        """
        self.api_url = api_url
        self.api_token = api_token
        self.namespaces = []
        self.session = requests.Session()
        self.session.headers.update({"content-type": "application/json", "Authorization": f"APIToken {api_token}"})
        # build hashmap with sites referenced by various objects. Initialize a multidimensional dictionary
        # self.sites = {"site": dict()}  # defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
        # self.sites = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
        self.site1 = {"site": dict()}

        logger.info(f"API URL: {self.api_url} -- Processing Namespace: {namespace if namespace else 'ALL'}")

        if not namespace:
            # get list of all namespaces
            response = self.get(self.build_url(URI_F5XC_NAMESPACE))

            if response:
                logger.debug(json.dumps(response.json(), indent=2))
                # Extracting namespaces names
                json_items = response.json()
                self.namespaces = [item['name'] for item in json_items['items']]
                logger.info(f"namespaces: {self.namespaces}")
            else:
                sys.exit(1)

        else:
            # check api url and validate given namespace
            response = self.get(self.build_url(f"{URI_F5XC_NAMESPACE}/{namespace}"))

            if response:
                logger.debug(json.dumps(response.json(), indent=2))
                self.namespaces = [namespace]
            else:
                sys.exit(1)

    def get(self, url: str = None) -> Response | bool:
        r = self.session.get(url)

        if 200 != r.status_code:
            logger.error("get failed for {} with {}".format(url, r.status_code))
            logger.info(f"get failed for  {url} with {r.status_code}")
            return False

        return r if r else False

    def build_url(self, uri: str = None) -> str:
        """

        :param uri:
        :return:
        """
        return "{}{}".format(self.api_url, uri)

    def run(self):
        import pprint
        pp = pprint.PrettyPrinter(indent=1)

        # Item = namedtuple('Item', ['namespace', 'lb_type'])
        items = list()

        for namespace in self.namespaces:
            for lb_type in F5XC_LOAD_BALANCER_TYPES:
                #items.append(Item(namespace, lb_type))
                items.append(self.build_url(URI_F5XC_LOAD_BALANCER.format(namespace=namespace, lb_type=lb_type)))

        response = list()

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_ds = {executor.submit(self.get, url=item): item for item in items}
            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    data = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (_data, exc))
                else:
                    #self.site1["site"].update(data["site"]) if data else None
                    response.append(data.json()["items"]) if data else None

        # pp.pprint(self.sites)
        # pp.pprint(response)
        self.process_load_balancers1(response)
        """
        for namespace in self.namespaces:
            for lb_type in F5XC_LOAD_BALANCER_TYPES:
                self.process_load_balancers(self.build_url(URI_F5XC_LOAD_BALANCER.format(namespace=namespace, lb_type=lb_type)), namespace)

            self.process_proxies(self.build_url(URI_F5XC_PROXIES.format(namespace=namespace)), namespace)
            self.process_origin_pools(self.build_url(URI_F5XC_ORIGIN_POOLS.format(namespace=namespace)), namespace)
        """

        # for namespace in self.namespaces:
        #    self.process_proxies(self.build_url(URI_F5XC_PROXIES.format(namespace=namespace)), namespace)
        #    self.process_origin_pools(self.build_url(URI_F5XC_ORIGIN_POOLS.format(namespace=namespace)), namespace)

        # get list of sites
        response = self.get(self.build_url(URI_F5XC_SITES))

        if response:
            logger.debug(json.dumps(response.json(), indent=2))
            json_items = response.json()

            for item in json_items['items']:
                # only add labels to sites that are referenced by a LB/origin_pool/proxys object
                if item['name'] in self.sites['site']:
                    self.sites['site'][item['name']]['labels'] = item['labels']

            # Dictionaries to store the sites with only origin pools and without origin pools or load balancers
            sites_with_only_origin_pools = []

            # Iterate through each site in the JSON data
            for site_name, site_info in self.sites['site'].items():
                has_origin_pool = 'origin_pools' in site_info
                has_load_balancer = 'loadbalancer' in site_info
                has_proxys = 'proxys' in site_info

                # Check if the site has origin pools only (and no load balancer)
                if has_origin_pool and not has_load_balancer and not has_proxys:
                    sites_with_only_origin_pools.append(site_name)

            # Print the results
            logger.info(f"\nSites with origin pools only: {sites_with_only_origin_pools}")

        else:
            sys.exit(1)

    def write_json_file(self, name: str = None):
        if name not in ['stdout', '-', '']:
            try:
                with open(name, 'w') as fd:
                    fd.write(json.dumps(self.sites, indent=2))
                    logger.info(f"{len(self.sites['site'])} sites and {len(self.sites['virtual_site'])} virtual sites written to {name}")
            except OSError as e:
                logger.info(f"Writing file {name} failed with error: {e}")
        else:
            logger.info(json.dumps(self.sites, indent=2))

    def read_json_file(self, name: str = None):
        try:
            with open(name, "r") as fd:
                self.sites = json.load(fd)
        except (FileNotFoundError, OSError) as e:
            logger.info(f"Reading file {name} failed with error: {e}")

    def process_load_balancers(self, url: str = None, namespace: str = None) -> dict | bool:
        """

        :param url:
        :param namespace:
        :return:
        """
        logger.info(f"process_load_balancers called for {url}")
        response = self.get(url)

        if response:
            r = dict()
            json_items = response.json()
            logger.debug(json.dumps(json_items, indent=2))

            for item in json_items['items']:
                name = item['name']
                logger.info(f"get item {url}/{name} ...")
                response = self.get(f"{url}/{name}")

                if response:
                    data = response.json()
                    logger.debug(json.dumps(data, indent=2))

                    if 'advertise_custom' in data['spec'] and 'advertise_where' in data['spec']['advertise_custom']:
                        for index, site_info in enumerate(data['spec']['advertise_custom']['advertise_where']):
                            if 'site' in site_info:
                                for site_type in site_info['site'].keys():
                                    if site_type in F5XC_SITE_TYPES:
                                        try:
                                            """
                                            r[site_type] = dict()
                                            site_name = site_info['site'][site_type]['name']
                                            r[site_type][site_name] = dict()
                                            r[site_type][site_name][namespace] = dict()
                                            r[site_type][site_name][namespace]['loadbalancer'] = dict()
                                            r[site_type][site_name][namespace]['loadbalancer'][name] = None
                                            # self.sites[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                                            r[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                                            """
                                            site_name = site_info['site'][site_type]['name']
                                            self.sites[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                                            logger.info(f"namespace {namespace} loadbalancer {name} {site_type} {site_name}")
                                        except Exception as e:
                                            logger.info("site_type:", site_type)
                                            logger.info("site_name:", site_name)
                                            logger.info("namespace:", namespace)
                                            logger.info("lb_name:", name)
                                            logger.info("system_metadata:", data['system_metadata'])
                                            logger.info("Exception:", e)
                else:
                    sys.exit(1)

            return r if r else False

        else:
            sys.exit(1)

    def process_load_balancers1(self, data: list) -> dict | bool:

        urls = list()
        response = list()
        for item in data:
            for lb in item:
                name = lb['name']

                for lb_type in F5XC_LOAD_BALANCER_TYPES:
                    url = self.build_url(URI_F5XC_LOAD_BALANCER.format(namespace=lb["namespace"], lb_type=lb_type))
                    logger.info(f"get item {url}/{name} ...")
                    #response = api_get(self.session, f"{url}/{name}")
                    #print("LB_RESPONSE:", response.json() if response else None)
                    urls.append(url)

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_to_ds = {executor.submit(self.get, url=url): url for url in urls}

                    for future in concurrent.futures.as_completed(future_to_ds):
                        _data = future_to_ds[future]

                        try:
                            data = future.result()
                        except Exception as exc:
                            print('%r generated an exception: %s' % (_data, exc))
                        else:
                            # self.site1["site"].update(data["site"]) if data else None
                            response.append(data.json()["items"]) if data else None
                            print(response)

        print(response)
        """
        logger.info(f"process_load_balancers called for {url}")
        response = api_get(self.session, url)

        if response:
            r = dict()
            json_items = response.json()
            logger.debug(json.dumps(json_items, indent=2))

            for item in json_items['items']:
                name = item['name']
                logger.info(f"get item {url}/{name} ...")
                response = api_get(self.session, f"{url}/{name}")

                if response:
                    data = response.json()
                    logger.debug(json.dumps(data, indent=2))

                    if 'advertise_custom' in data['spec'] and 'advertise_where' in data['spec']['advertise_custom']:
                        for index, site_info in enumerate(data['spec']['advertise_custom']['advertise_where']):
                            if 'site' in site_info:
                                for site_type in site_info['site'].keys():
                                    if site_type in F5XC_SITE_TYPES:
                                        try:
                                            
                                            #r[site_type] = dict()
                                            #site_name = site_info['site'][site_type]['name']
                                            #r[site_type][site_name] = dict()
                                            #r[site_type][site_name][namespace] = dict()
                                            #r[site_type][site_name][namespace]['loadbalancer'] = dict()
                                            #r[site_type][site_name][namespace]['loadbalancer'][name] = None
                                            # self.sites[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                                            #r[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                                            site_name = site_info['site'][site_type]['name']
                                            self.sites[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                                            logger.info(f"namespace {namespace} loadbalancer {name} {site_type} {site_name}")
                                        except Exception as e:
                                            print("site_type:", site_type)
                                            print("site_name:", site_name)
                                            print("namespace:", namespace)
                                            print("lb_name:", name)
                                            print("system_metadata:", data['system_metadata'])
                                            print("Exception:", e)
                else:
                    sys.exit(1)

            return r if r else False

        else:
            sys.exit(1)
        """

    def process_proxies(self, url: str = None, namespace: str = None):
        """

        :param url:
        :param namespace:
        :return:
        """
        logger.info(f"process_proxies called for {url}")
        response = self.get(url)

        if response:
            json_items = response.json()
            logger.debug(json.dumps(json_items, indent=2))

            for item in json_items['items']:
                name = item['name']
                logger.info(f"get item {url}/{name} ...")
                response = self.get(f"{url}/{name}")

                if response:
                    data = response.json()
                    logger.debug(json.dumps(data, indent=2))

                    site_virtual_sites = data['spec'].get('site_virtual_sites', {})
                    advertise_where = site_virtual_sites.get('advertise_where', [])

                    for site_info in advertise_where:
                        site = site_info.get('site', {})
                        for site_type in ['site', 'virtual_site']:
                            if site_type in site:
                                site_name = site[site_type].get('name')
                                if site_name:
                                    self.sites[site_type][site_name][namespace]['proxys'][name] = data['system_metadata']
                                    logger.info(f"namespace {namespace} proxys {name} {site_type} {site_name}")
                else:
                    sys.exit(1)
        else:
            sys.exit(1)

    def process_origin_pools(self, url: str = None, namespace: str = None):
        """

        :param url:
        :param namespace:
        :return:
        """
        logger.info(f"process_origin_pools called for {url}")
        response = self.get(url)

        if response:
            json_items = response.json()
            logger.debug(json.dumps(json_items, indent=2))

            for item in json_items['items']:
                name = item['name']
                logger.info(f"get item {url}/{name} ...")
                response = self.get(f"{url}/{name}")

                if response:
                    data = response.json()
                    logger.debug(json.dumps(data, indent=2))
                    origin_servers = data['spec'].get('origin_servers', [])

                    for site_info in origin_servers:
                        for key in F5XC_ORIGIN_SERVER_TYPES:
                            site_locator = site_info.get(key, {}).get('site_locator', {})

                            for site_type, site_data in site_locator.items():
                                site_name = site_data.get('name')

                                if site_name:
                                    self.sites[site_type][site_name][namespace]['origin_pools'][name] = data['system_metadata']
                                    logger.info(f"namespace {namespace} origin_pools {name} {site_type} {site_name}")
                else:
                    sys.exit(1)
        else:
            sys.exit(1)


def main():
    logger.info(f"Application {os.path.basename(__file__)} started...")

    # Create the parser
    parser = argparse.ArgumentParser(description="Get F5 XC Sites command line arguments")

    # Add arguments
    parser.add_argument('-n', '--namespace', type=str,
                        help='Namespace (not setting this option will process all namespaces)', required=False, default='')
    parser.add_argument('-a', '--apiurl', type=str, help='F5 XC API URL',
                        required=False, default='')
    parser.add_argument('-t', '--token', type=str, help='F5 XC API Token',
                        required=False, default='')
    parser.add_argument('-f', '--file', type=str, help='write site list to file',
                        required=False, default=Path(__file__).stem + '.json')
    parser.add_argument('-l', '--log', type=str, help='set log level: INFO or DEBUG',
                        required=False, default="INFO")

    # Parse the arguments
    args = parser.parse_args()
    api_url = args.apiurl if args.apiurl else os.environ.get('f5xc_api_url')
    api_token = args.token if args.token else os.environ.get('f5xc_api_token')

    if not api_url or not api_token:
        parser.print_help()
        sys.exit(1)

    level = getattr(logging, args.log.upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid log level: %s' % args.log.upper())
    logging.basicConfig(level=level)

    q = Api(api_url=api_url, api_token=api_token, namespace=args.namespace)
    q.run()
    q.write_json_file(args.file)

    logger.info(f"Application {os.path.basename(__file__)} finished")


if __name__ == '__main__':
    main()
