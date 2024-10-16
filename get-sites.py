#!/usr/bin/env python3

import argparse
import json
import logging
import os
import requests
import sys
from pprint import pprint
from pathlib import Path
from collections import defaultdict

# Configure the logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
    filename=Path(__file__).stem + '.log',
    filemode='w'  # 'w' for overwrite, 'a' for append
)


def process_loadbalancers(url, sites, headers, namespace):
    logging.info(f"process_loadbalancers called for {url}")

    response = requests.get(url, headers=headers)

    if 200 != response.status_code:
        logging.error("get failed for {} with {}".format(
            url, response.status_code))
        print(f"get failed for  {url} with {response.status_code}")
        sys.exit(1)

    json_items = response.json()
    logging.debug(json.dumps(json_items, indent=2))

    for item in json_items['items']:
        name = item['name']
        logging.info(f"get item {url}/{name} ...")
        response = requests.get(url + "/" + name, headers=headers)
        if 200 != response.status_code:
            logging.error(
                "get failed for {}/{} with {}".format(url, name, response.status_code))
            print(f"get failed for {url}/{name} with {response.status_code}")
            sys.exit(1)

        data = response.json()
        logging.debug(json.dumps(data, indent=2))

        advertise_custom = data['spec'].get('advertise_custom', {})
        advertise_where = advertise_custom.get('advertise_where', [])

        for site_info in advertise_where:
            site_type = next(
                (k for k in ['site', 'virtual_site'] if k in site_info), None)
            if site_type:
                site_name = site_info[site_type].get(site_type, {}).get('name')
                if site_name:
                    sites[site_type][site_name][namespace]['loadbalancer'][name] = data['system_metadata']
                    print(f"namespace {namespace} loadbalancer {name} {
                          site_type} {site_name}", file=sys.stderr)


def process_proxys(url, sites, headers, namespace):
    logging.info(f"process_proxys called for {url}")

    response = requests.get(url, headers=headers)

    if 200 != response.status_code:
        logging.error("get failed for {} with {}".format(
            url, response.status_code))
        print(f"get failed for  {url} with {response.status_code}")
        sys.exit(1)

    json_items = response.json()
    logging.debug(json.dumps(json_items, indent=2))

    for item in json_items['items']:
        name = item['name']
        logging.info(f"get item {url}/{name} ...")
        response = requests.get(url + "/" + name, headers=headers)
        if 200 != response.status_code:
            logging.error(
                "get failed for {}/{} with {}".format(url, name, response.status_code))
            print(f"get failed for {url}/{name} with {response.status_code}")
            sys.exit(1)

        data = response.json()
        logging.debug(json.dumps(data, indent=2))

        site_virtual_sites = data['spec'].get('site_virtual_sites', {})
        advertise_where = site_virtual_sites.get('advertise_where', [])

        for site_info in advertise_where:
            site = site_info.get('site', {})
            for site_type in ['site', 'virtual_site']:
                if site_type in site:
                    site_name = site[site_type].get('name')
                    if site_name:
                        sites[site_type][site_name][namespace]['proxys'][name] = data['system_metadata']
                        print(f"namespace {namespace} proxys {name} {
                              site_type} {site_name}", file=sys.stderr)


def process_origin_pools(url, sites, headers, namespace):
    logging.info(f"process_origin_pools called for {url}")

    response = requests.get(url, headers=headers)

    if 200 != response.status_code:
        logging.error("get failed for {} with {}".format(
            url, response.status_code))
        print(f"get failed for  {url} with {response.status_code}")
        sys.exit(1)

    json_items = response.json()
    logging.debug(json.dumps(json_items, indent=2))

    for item in json_items['items']:
        name = item['name']
        logging.info(f"get item {url}/{name} ...")
        response = requests.get(url + "/" + name, headers=headers)
        if 200 != response.status_code:
            logging.error(
                "get failed for {}/{} with {}".format(url, name, response.status_code))
            print(f"get failed for {url}/{name} with {response.status_code}")
            sys.exit(1)

        data = response.json()
        logging.debug(json.dumps(data, indent=2))

        origin_servers = data['spec'].get('origin_servers', [])

        for site_info in origin_servers:
            for key in ['private_ip', 'k8s_service', 'consul_service', 'private_name']:
                site_locator = site_info.get(key, {}).get('site_locator', {})
                for site_type, site_data in site_locator.items():
                    site_name = site_data.get('name')
                    if site_name:
                        sites[site_type][site_name][namespace]['origin_pools'][name] = data['system_metadata']
                        print(f"namespace {namespace} origin_pools {name} {
                              site_type} {site_name}", file=sys.stderr)


def main():
    logging.info(f"{__file__} started")

    # Create the parser
    parser = argparse.ArgumentParser(
        description="Get F5 XC Sites line arguments.")

    # Add arguments
    parser.add_argument('-n', '--namespace', type=str,
                        help='Namespace (use "" to parse all namespaces)', required=False, default="default")
    parser.add_argument('-a', '--apiurl', type=str, help='F5 XC API URL',
                        required=False, default=os.environ.get('f5xc_api_url', ''))
    parser.add_argument('-t', '--token', type=str, help='F5 XC API Token',
                        required=False, default=os.environ.get('f5xc_api_token', ''))
    parser.add_argument('-f', '--file', type=str, help='write site list to file',
                        required=False, default=Path(__file__).stem + '.json')

    # Parse the arguments
    args = parser.parse_args()
    if '' == args.apiurl or '' == args.token:
        parser.print_help()
        sys.exit(1)

    logging.info(f"apiurl {args.apiurl} namespace {args.namespace}")

    headers = {}
    headers["content-type"] = "application/json"
    headers["Authorization"] = "APIToken {}".format(args.token)

    if "" == args.namespace:
        # get list of all namespaces
        response = requests.get(
            args.apiurl + "/web/namespaces", headers=headers)

        if 200 != response.status_code:
            logging.error("get all namespaces failed with {}".format(
                response.status_code))
            print(
                f"get all namespaces via {args.apiurl} failed with {response.status_code}")
            sys.exit(1)

        logging.debug(json.dumps(response.json(), indent=2))
        # Extracting the names of namespaces
        json_items = response.json()
        namespaces = [item['name'] for item in json_items['items']]

    else:
        # check api url and validate given namespace
        response = requests.get(
            args.apiurl + "/web/namespaces/" + args.namespace, headers=headers)

        if 200 != response.status_code:
            logging.error("get namespace {} failed with {}".format(
                args.namespace, response.status_code))
            print(
                f"get namespace {args.namespace} via {args.apiurl} failed with {response.status_code}")
            sys.exit(1)

        logging.debug(json.dumps(response.json(), indent=2))
        namespaces = [args.namespace]

    # build hashmap with sites referenced by various objects
    # Initialize a multi-dimensional dictionary
    sites = defaultdict(lambda: defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))))

    sites['namespaces'] = namespaces

    for namespace in namespaces:

        for type in ["http_loadbalancers", "tcp_loadbalancers"]:
            process_loadbalancers(args.apiurl + "/config/namespaces/" +
                                  namespace + "/" + type, sites, headers, namespace)

        process_proxys(args.apiurl + "/config/namespaces/" +
                       namespace + "/proxys", sites, headers, namespace)
        process_origin_pools(args.apiurl + "/config/namespaces/" +
                             namespace + "/origin_pools", sites, headers, namespace)

    # get list of sites

    response = requests.get(
        args.apiurl + "/config/namespaces/system/sites", headers=headers)

    if 200 != response.status_code:
        logging.error("get sites failed with {}".format(
            response.status_code))
        print(
            f"get sites via {args.apiurl} failed with {response.status_code}")
        sys.exit(1)

    logging.debug(json.dumps(response.json(), indent=2))

    json_items = response.json()
    for item in json_items['items']:
        # only add labels to sites that are referenced by a LB/origin_pool/proxys object
        if item['name'] in sites['site']:
            sites['site'][item['name']]['site_labels'] = item['labels']

    # Dictionaries to store the sites with only origin pools and without origin pools or load balancers
    sites_with_only_origin_pools = []
    sites_with_neither = []

    # Iterate through each site in the JSON data
    # TODO fix this to work across namespaces
    for site_name, _ in sites['site'].items():
        for namespace, site_info in sites['site'][site_name].items():
            has_origin_pool = 'origin_pools' in site_info
            has_load_balancer = 'loadbalancer' in site_info
            has_proxys = 'proxys' in site_info

            # Check if the site has only origin pools (and no load balancer)
            if has_origin_pool and not has_load_balancer and not has_proxys:
                sites_with_only_origin_pools.append(site_name)

    sites['sites_with_only_origin_pools'] = sites_with_only_origin_pools
    logging.debug(f"\nSites with only origin pools: {
                  sites_with_only_origin_pools}")

    if args.file not in ['stdout', '-', '']:
        with open(args.file, 'w') as file:
            file.write(json.dumps(sites, indent=2))
            print(f"{len(sites['site'])} sites and {
                  len(sites['virtual_site'])} virtual sites written to {args.file}")
    else:
        print(json.dumps(sites, indent=2))

    logging.info("Application finished")


if __name__ == '__main__':
    main()
