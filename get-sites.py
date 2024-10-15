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


def process_loadbalancers(url: str = None, sites: str = None, headers: dict = None, namespace: str = ""):
    logger.info(f"process_loadbalancers called for {url}")

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

        if 'advertise_custom' in data['spec'] and 'advertise_where' in data['spec']['advertise_custom']:
            for index, site_info in enumerate(data['spec']['advertise_custom']['advertise_where']):
                if 'site' in site_info:
                    for site_type in site_info['site'].keys():
                        if site_type in ["site", "virtual_site"]:
                            site_name = site_info['site'][site_type]['name']
                            sites[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
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
    logger.info(f"{__file__} started")

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
    if not args.apiurl or not args.token:
        api_url = os.environ.get('f5xc_api_token')
        api_token = os.environ.get('f5xc_api_url')

        if not api_url or not api_token:

            parser.print_help()
            sys.exit(1)

    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log.upper())
    logging.basicConfig(level=numeric_level)

    logger.info(f"apiurl {args.apiurl} namespace {args.namespace}")

    headers = {"content-type": "application/json", "Authorization": "APIToken {}".format(args.token)}

    if "" == args.namespace:
        # get list of all namespaces
        response = requests.get(args.apiurl + "/web/namespaces", headers=headers)

        if 200 != response.status_code:
            logger.error("get all namespaces failed with {}".format(response.status_code))
            logger.info(f"get all namespaces via {args.apiurl} failed with {response.status_code}")
            sys.exit(1)

        logger.debug(json.dumps(response.json(), indent=2))
        # Extracting the names of namespaces
        json_items = response.json()
        namespaces = [item['name'] for item in json_items['items']]
        logger.info(f"namespaces {namespaces}")

    else:
        # check api url and validate given namespace
        response = requests.get(args.apiurl + "/web/namespaces/" + args.namespace, headers=headers)

        if 200 != response.status_code:
            logger.error("get namespace {} failed with {}".format(args.namespace, response.status_code))
            logger.info(f"get namespace {args.namespace} via {args.apiurl} failed with {response.status_code}")
            sys.exit(1)

        logger.debug(json.dumps(response.json(), indent=2))
        namespaces = [args.namespace]

    # build hashmap with sites referenced by various objects
    # Initialize a multidimensional dictionary
    sites = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))

    for namespace in namespaces:
        for _type in ["http_loadbalancers", "tcp_loadbalancers"]:
            process_loadbalancers(args.apiurl + "/config/namespaces/" +
                                  namespace + "/" + _type, sites, headers, namespace)

        process_proxys(args.apiurl + "/config/namespaces/" +
                       namespace + "/proxys", sites, headers, namespace)
        process_origin_pools(args.apiurl + "/config/namespaces/" +
                             namespace + "/origin_pools", sites, headers, namespace)

    # get list of sites
    response = requests.get(args.apiurl + "/config/namespaces/system/sites", headers=headers)

    if 200 != response.status_code:
        logger.error("get sites failed with {}".format(response.status_code))
        logger.info(f"get sites via {args.apiurl} failed with {response.status_code}")
        sys.exit(1)

    logger.debug(json.dumps(response.json(), indent=2))

    json_items = response.json()
    for item in json_items['items']:
        # only add labels to sites that are referenced by a LB/origin_pool/proxys object
        if item['name'] in sites['site']:
            sites['site'][item['name']]['labels'] = item['labels']

    if args.file not in ['stdout', '-', '']:
        with open(args.file, 'w') as file:
            file.write(json.dumps(sites, indent=2))
            logger.info(f"{len(sites['site'])} sites and {len(sites['virtual_site'])} virtual sites written to {args.file}")
    else:
        logger.info(json.dumps(sites, indent=2))

    # Dictionaries to store the sites with only origin pools and without origin pools or load balancers
    sites_with_only_origin_pools = []

    # Iterate through each site in the JSON data
    for site_name, site_info in sites['site'].items():
        has_origin_pool = 'origin_pools' in site_info
        has_load_balancer = 'loadbalancer' in site_info
        has_proxys = 'proxys' in site_info

        # Check if the site has only origin pools (and no load balancer)
        if has_origin_pool and not has_load_balancer and not has_proxys:
            sites_with_only_origin_pools.append(site_name)

    # Print the results
    logger.info(f"\nSites with only origin pools: {sites_with_only_origin_pools}")
    logger.info("Application finished")


if __name__ == '__main__':
    main()
