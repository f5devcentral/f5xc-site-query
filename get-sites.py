#!/usr/bin/env python3

import argparse
import json
import logging
import os
import requests
import sys
# from pprint import pprint
from pathlib import Path
from collections import defaultdict

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

URI_F5XC_NAMESPACE = "/web/namespaces"
URI_F5XC_SITES = "/config/namespaces/system/sites"
URI_F5XC_LOAD_BALANCER = "/config/namespaces/{namespace}/{lb_type}"
F5XC_LOAD_BALANCER_TYPES = ["http_loadbalancers", "tcp_loadbalancers"]


class Query(object):
    def __init__(self, api_url: str = None, api_token: str = None, namespace: str = None, json_file: str = None):
        self.api_url = api_url
        self.api_token = api_token
        self.headers = {"content-type": "application/json", "Authorization": "APIToken {}".format(api_token)}
        self.namespaces = []
        # build hashmap with sites referenced by various objects
        # Initialize a multidimensional dictionary
        self.sites = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))

        logger.info(f"API URL: {self.api_url} -- Namespace: {namespace}")

        if namespace:
            # get list of all namespaces
            response = requests.get(self.api_url + URI_F5XC_NAMESPACE, headers=self.headers)

            if 200 != response.status_code:
                logger.error("get all namespaces failed with {}".format(response.status_code))
                logger.info(f"get all namespaces via {self.api_url} failed with {response.status_code}")
                sys.exit(1)

            logger.debug(json.dumps(response.json(), indent=2))
            # Extracting the names of namespaces
            json_items = response.json()
            self.namespaces = [item['name'] for item in json_items['items']]
            logger.info(f"namespaces: {self.namespaces}")

        else:
            # check api url and validate given namespace
            response = requests.get(self.api_url + URI_F5XC_NAMESPACE + "/" + namespace, headers=self.headers)

            if 200 != response.status_code:
                logger.error("get namespace {} failed with {}".format(namespace, response.status_code))
                logger.info(f"get namespace {namespace} from {self.api_url} failed with {response.status_code}")
                sys.exit(1)

            logger.debug(json.dumps(response.json(), indent=2))
            self.namespaces = [namespace]

        for namespace in self.namespaces:
            for lb_type in F5XC_LOAD_BALANCER_TYPES:
                self.process_loadbalancers("{}{}".format(self.api_url, URI_F5XC_LOAD_BALANCER.format(namespace, lb_type)), namespace)

            process_proxys(self.api_url + "/config/namespaces/" +
                           namespace + "/proxys", self.sites, self.headers, namespace)
            process_origin_pools(self.api_url + "/config/namespaces/" +
                                 namespace + "/origin_pools", self.sites, self.headers, namespace)

        # get list of sites
        response = requests.get(self.api_url + URI_F5XC_SITES, headers=self.headers)

        if 200 != response.status_code:
            logger.error("get sites failed with {}".format(response.status_code))
            logger.info(f"get sites via {self.api_url} failed with {response.status_code}")
            sys.exit(1)

        logger.debug(json.dumps(response.json(), indent=2))

        json_items = response.json()
        for item in json_items['items']:
            # only add labels to sites that are referenced by a LB/origin_pool/proxys object
            if item['name'] in self.sites['site']:
                self.sites['site'][item['name']]['labels'] = item['labels']

        if json_file not in ['stdout', '-', '']:
            with open(json_file, 'w') as file:
                file.write(json.dumps(self.sites, indent=2))
                logger.info(f"{len(self.sites['site'])} sites and {len(self.sites['virtual_site'])} virtual sites written to {json_file}")
        else:
            logger.info(json.dumps(self.sites, indent=2))

        # Dictionaries to store the sites with only origin pools and without origin pools or load balancers
        sites_with_only_origin_pools = []

        # Iterate through each site in the JSON data
        for site_name, site_info in self.sites['site'].items():
            has_origin_pool = 'origin_pools' in site_info
            has_load_balancer = 'loadbalancer' in site_info
            has_proxys = 'proxys' in site_info

            # Check if the site has only origin pools (and no load balancer)
            if has_origin_pool and not has_load_balancer and not has_proxys:
                sites_with_only_origin_pools.append(site_name)

        # Print the results
        logger.info(f"\nSites with only origin pools: {sites_with_only_origin_pools}")

    def process_loadbalancers(self, url: str = None, namespace: str = ""):
        logger.info(f"process_loadbalancers called for {url}")

        response = requests.get(url, headers=self.headers)
        if 200 != response.status_code:
            logger.error("get failed for {} with {}".format(url, response.status_code))
            logger.info(f"get failed for  {url} with {response.status_code}")
            sys.exit(1)

        json_items = response.json()
        logger.debug(json.dumps(json_items, indent=2))

        for item in json_items['items']:
            name = item['name']
            logger.info(f"get item {url}/{name} ...")

            response = requests.get(url + "/" + name, headers=self.headers)
            if 200 != response.status_code:
                logger.error("get failed for {}/{} with {}".format(url, name, response.status_code))
                logger.info(f"get failed for {url}/{name} with {response.status_code}")
                sys.exit(1)

            data = response.json()
            logger.debug(json.dumps(data, indent=2))

            if 'advertise_custom' in data['spec'] and 'advertise_where' in data['spec']['advertise_custom']:
                for index, site_info in enumerate(data['spec']['advertise_custom']['advertise_where']):
                    if 'site' in site_info:
                        for site_type in site_info['site'].keys():
                            if site_type in ["site", "virtual_site"]:
                                site_name = site_info['site'][site_type]['name']
                                self.sites[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                                logger.info(f"namespace {namespace} loadbalancer {name} {site_type} {site_name}")
        #                    else:
        #                        logger.info(f"site_type={site_type}", json.dumps(site_info['site'][site_type], indent=2))


def process_proxys(url, sites, headers, namespace):
    logger.info(f"process_proxys called for {url}")

    response = requests.get(url, headers=headers)

    if 200 != response.status_code:
        logger.error("get failed for {} with {}".format(
            url, response.status_code))
        logger.info(f"get failed for  {url} with {response.status_code}")
        sys.exit(1)

    json_items = response.json()
    logger.debug(json.dumps(json_items, indent=2))

    for item in json_items['items']:
        name = item['name']
        logger.info(f"get item {url}/{name} ...")
        response = requests.get(url + "/" + name, headers=headers)
        if 200 != response.status_code:
            logger.error("get failed for {}/{} with {}".format(url, name, response.status_code))
            logger.info(f"get failed for {url}/{name} with {response.status_code}")
            sys.exit(1)

        data = response.json()
        logger.debug(json.dumps(data, indent=2))

        if 'site_virtual_sites' in data['spec'] and 'advertise_where' in data['spec']['site_virtual_sites']:
            for index, site_info in enumerate(data['spec']['site_virtual_sites']['advertise_where']):
                if 'site' in site_info:
                    for site_type in site_info['site'].keys():
                        if site_type in ["site", "virtual_site"]:
                            site_name = site_info['site'][site_type]['name']
                            sites[site_type][site_name][namespace]['proxys'][name] = data['system_metadata']
                            logger.info(f"namespace {namespace} proxys {name} {site_type} {site_name}")


def process_origin_pools(url, sites, headers, namespace):
    logger.info(f"process_origin_pools called for {url}")

    response = requests.get(url, headers=headers)
    if 200 != response.status_code:
        logger.error("get failed for {} with {}".format(url, response.status_code))
        logger.info(f"get failed for  {url} with {response.status_code}")
        sys.exit(1)

    json_items = response.json()
    logger.debug(json.dumps(json_items, indent=2))

    for item in json_items['items']:
        name = item['name']
        logger.info(f"get item {url}/{name} ...")

        response = requests.get(url + "/" + name, headers=headers)
        if 200 != response.status_code:
            logger.error("get failed for {}/{} with {}".format(url, name, response.status_code))
            logger.info(f"get failed for {url}/{name} with {response.status_code}")
            sys.exit(1)

        data = response.json()
        logger.debug(json.dumps(data, indent=2))

        if 'origin_servers' in data['spec']:
            for site_info in data['spec']['origin_servers']:
                # Iterate over the keys to check
                for key in ['private_ip', 'k8s_service', 'consul_service', 'private_name']:
                    if key in site_info:
                        for site_type in site_info[key]['site_locator'].keys():
                            site_name = site_info[key]['site_locator'][site_type]['name']
                            # sites[site_name] = sites.get(site_name, 0) + 1
                            sites[site_type][site_name][namespace]['origin_pools'][name] = data['system_metadata']
                            logger.info(f"namespace {namespace} origin_pools {name} {site_type} {site_name}")


def main():
    logger.info(f"Application {__file__} started...")

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

    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log.upper())
    logging.basicConfig(level=numeric_level)

    logger.info(f"Application {__file__} finished")


if __name__ == '__main__':
    main()
