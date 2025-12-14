"""
authors: cklewar
"""


import json
import re
import sys

from logging import Logger
from typing import Any, Tuple, List

import jsondiff
import requests
from prettytable import PrettyTable, TableStyle
from requests import Response

import lib.const as c
from lib.loader import load_module
from lib.output.xlsx import Xlsx


def custom_key_sorter(key: str) -> Tuple[int, int, str]:
    """
    Sorting function for Node keys.
    Priority 1: Node-related keys (node0_*, node1_*, etc.)
    Sorts by node number (n=0, 1, 2...), then alphabetically.
    """
    if key.startswith('node') and key[4:5].isdigit():
        match = re.match(r'node(\d+)(.*)', key)
        if match:
            node_number = int(match.group(1))
            # Returns: (Priority Level, Node Index, Key Name)
            return 1, node_number, key

    # Priority 0: All other keys
    # Returns: (Priority Level, Sub-Index, Key Name)
    return 0, 0, key


def build_master_key_list(source_keys: List[str], target_keys: List[str]) -> List[str]:
    """
    Builds the final, sorted master list of keys by inserting target-only keys
    into the logical group structure of the source keys.
    """

    source_set = set(source_keys)
    target_set = set(target_keys)

    # Keys that exist only in the Target
    target_only_set = target_set - source_set

    # Master list of keys
    master_keys = []

    # Regular keys and keys that exist in both
    for key in source_keys:
        master_keys.append(key)

    # Identify and sort Target-Only Keys
    # Note: custom_key_sorter is assumed to exist and sort based on 'node' numbers.
    target_only_keys_sorted = sorted(list(target_only_set), key=custom_key_sorter)

    # Supplement the master list with Target-Only Keys at the correct position
    final_master_keys = []

    # Iterate over the Source list and try to insert target keys in between
    for key in master_keys:
        final_master_keys.append(key)

        # Logic: After each logical group in Source (Node, EFP/FPP, Namespace-Pools, etc.),
        # we check if Target-Only Keys fall into this group.

        # Insert all Target-Only Node keys AFTER the last Source Node key (e.g., after node2_interfaces)

        if key.startswith('node') and key[4:5].isdigit():
            # Find the highest node number in the Source list (e.g., 2)
            node_numbers = [int(re.match(r'node(\d+)', k).group(1)) for k in final_master_keys if re.match(r'node\d+', k)]
            max_source_node = max(node_numbers) if node_numbers else -1

            # Check if this is the last node key in the Source list (nodeX_interfaces)
            # This is a heuristic, based on the assumption that node_interfaces is the last in the group.
            # Alternative: Insert all Target-Only Nodes after the last node key of the Source
            if key == f'node{max_source_node}_interfaces':
                # Filter Target-Only Node keys (e.g., node3_interfaces, node4_interfaces,...)
                target_only_node_keys = [k for k in target_only_keys_sorted
                                         if re.match(r'node(\d+)', k) and int(re.match(r'node(\d+)', k).group(1)) > max_source_node]

                if target_only_node_keys:
                    final_master_keys.extend(target_only_node_keys)

                    # Remove them from the Target-Only list to prevent double use later
                    target_only_set -= set(target_only_node_keys)
                    target_only_keys_sorted = sorted(list(target_only_set), key=custom_key_sorter)

    # --- Remaining Target-Only Keys (Namespace Pools, etc.) ---
    # These are appended at the end, as they do not have a direct relation to a specific
    # Source key at a particular position (other than the Nodes).
    # Here they are simply added as a second 'Target-Only' group at the very end.
    if target_only_keys_sorted:
        final_master_keys.extend(target_only_keys_sorted)

    return final_master_keys

def format_list_with_newlines(value: Any) -> Any:
    """
    Converts a Python list into a string, displaying a maximum of
    two list elements per line, regardless of total length.
    """
    if isinstance(value, list):
        formatted_lines = []

        # Iterate over the list in steps of 2 (i.e., i, i+2, i+4, ...)
        for i in range(0, len(value), 2):
            # Take the current element (value[i])
            line = str(value[i])

            # Check if there is a next element (value[i+1])
            if i + 1 < len(value):
                # If yes, append the next element to the current line
                line += ', ' + str(value[i + 1])

            formatted_lines.append(line)

        # If there's only one line, return the string representation without explicit newlines
        if len(formatted_lines) <= 1:
            return str(value)

        # Join all lines with a newline character.
        # Prepend a newline for better visual alignment in the table cell.
        return '[\'' + ',\n'.join(formatted_lines) + '\']'

    # Return the value unchanged if it's not a list
    return value


class Api(object):
    """
    Represents the query API.

    Attributes
    ----------
    _logger: logger instance
    _api_url : str
        F5XC API URL
    _api_token : str
        F5XC API token
    _session: request.Session
        http session
    _workers: int
       maximum number of workers
    _data: dict
        inventory data structure. Filled with data by various modules. Items and attributes out of this ds used for compare function.
        Inventory structure:

        site
            <site_name>
                kind
                main_node_count
                metadata
                spec
                sms (for secure mesh based sites)
                legacy (for legacy object based sites)
                sub_kind
                worker_node_count
                efp
                fpp
                bgp
                dc_cluster_group
                nodes
                    <node_name>
                        interfaces
                        hw_info
                namespaces
                    loadbalancer
                        <lb_type> e.g. http/tcp
                            <loadbalancer_name>
                                spec
                                metadata
                                system_metadata
                    proxys
                        <proxy_name>
                            spec
                                metadata
                                system_metadata
                smg
                    <smg_name>
                        spec
                        metadata
                vsites [list of virtual site names]
        virtual_site
            <virtual_site_name>
                namespaces
                    loadbalancer
                        <lb_type> e.g. http/tcp
                            <loadbalancer_name>
                                spec
                                metadata
                                system_metadata
                    proxys
                        <proxy_name>
                            spec
                                metadata
                                system_metadata
        namespaces [list of namespace names]
        failed_sites { <site_name>: <site_status> } e.g. "ce-ga-singlenic-azure": "FAILED"

    Methods
    -------
    build_url(uri=None)
        builds api url based on uri
    get(url: str = None)
        http get request
    read_json_file(name: str = None)
        read json data from file name
    write_string_file(name=None, data=None)
        writes data string to file
    write_json_file(name=None)
        writes data to json file
    run()
        run the specific processor and build ds
    compare()
        compare any previous data set with current data set
    """

    def __init__(self, logger: Logger = None, api_url: str = None, api_token: str = None, namespace: str = None, site: str = None, workers: int = 10):
        """
        Initialize API object. Stores session state and allows to run data processing methods.

        :param api_url: F5XC API URL
        :param api_token: F5XC API token
        :param namespace: F5XC namespace
        :param site: F5XC site
        :param workers: Maximum number of workers for concurrent processing
        """

        self._logger = logger
        self._data = dict()
        for key in c.SITE_TYPES:
            self._data[key] = dict()
        self._api_url = api_url
        self._api_token = api_token
        self._site = site
        self._workers = workers
        self._session = requests.Session()
        self._session.headers.update({"content-type": "application/json", "Authorization": f"APIToken {api_token}"})
        self.must_break = False

        self.logger.info(f"API URL: {self.api_url} -- Processing Namespace: {namespace if namespace else 'ALL'}")

        if not namespace:
            # get list of all namespaces
            response = self.get(self.build_url(c.URI_F5XC_NAMESPACE))

            if response:
                self.logger.debug(json.dumps(response.json(), indent=2))
                namespaces = response.json()
                self._data['namespaces'] = [item['name'] for item in namespaces['items']]
                self.logger.info(f"Processing {len(self.data['namespaces'])} available namespaces")
            else:
                sys.exit(1)

        else:
            # check api url and validate given namespace
            response = self.get(self.build_url(f"{c.URI_F5XC_NAMESPACE}/{namespace}"))

            if response:
                self.logger.debug(json.dumps(response.json(), indent=2))
                self._data['namespaces'] = [namespace]
            else:
                sys.exit(1)

    @property
    def logger(self):
        return self._logger

    @property
    def data(self):
        return self._data

    @property
    def api_url(self):
        return self._api_url

    @property
    def api_token(self):
        return self._api_token

    @property
    def site(self):
        return self._site

    @property
    def session(self):
        return self._session

    @property
    def workers(self):
        return self._workers

    def build_url(self, uri: str = None) -> str:
        """
        Build url from api url + resource uri
        :param uri: the resource uri
        :return: url string
        """
        return "{}{}".format(self.api_url, uri)

    def get(self, url: str = None) -> Response | bool:
        """
        Run HTTP GET on a given url
        :param url: Actual URL to run GET request on
        :return: requests.Response
        """
        r = self.session.get(url)

        if 200 != r.status_code:
            if r.status_code == 401 or r.status_code == 403:
                self.logger.info("get failed for {} with authentication error: <{}>".format(url, r.status_code))
            self.logger.debug("get failed for {} with {}".format(url, r.status_code))
            return False

        return r if r else False

    def read_json_file(self, name: str = None) -> Any | None:
        """
        Read json data from file.
        :param name: file name
        :return:
        """
        try:
            with open(name, 'r') as fd:
                data = json.load(fp=fd)
                if c.SITES_KEY in data and c.VIRTUAL_SITES_KEY in data:
                    self.logger.info(
                        f"{len(data[c.SITES_KEY])} {c.SITES_KEY if len(data[c.SITES_KEY]) > 1 else c.SITES_KEY} and {len(data[c.VIRTUAL_SITES_KEY])} virtual {c.SITES_KEY if len(data[c.VIRTUAL_SITES_KEY]) > 1 else c.SITES_KEY} read from {name}")
                    return data
                else:
                    self.logger.info(f"Error reading data from file {name}. No site data available")
        except OSError as e:
            self.logger.info(f"Reading file {name} failed with error: {e}")
            return None

    def write_json_file(self, name: str = None):
        """
        Write json to file
        :param name: The file name to write json into
        :return:
        """
        if name not in ['stdout', '-', '']:
            try:
                with open(name, 'w') as fd:
                    if "filter_expressions_per_virtual_site" in self.data:
                        del self.data["filter_expressions_per_virtual_site"]
                    fd.write(json.dumps(self.data, indent=2))
                    self.logger.info(
                        f"{len(self.data[c.SITES_KEY])} {'sites' if len(self.data[c.SITES_KEY]) > 1 else c.SITES_KEY} and {len(self.data[c.VIRTUAL_SITES_KEY])} virtual {'sites' if len(self.data[c.VIRTUAL_SITES_KEY]) > 1 else c.SITES_KEY} written to {name}")
            except OSError as e:
                self.logger.info(f"Writing file {name} failed with error: {e}")
        else:
            self.logger.info(json.dumps(self.data, indent=2))

    def write_string_file(self, name: str = None, data: str = None):
        """
        Write string to file
        :param name: the file name
        :param data: str data to write to file
        :return:
        """

        if name not in ['stdout', '-', '']:
            try:
                with open(name, 'w') as fd:
                    fd.write(data)
                    self.logger.info(f"wrote {len(data.encode('utf-8'))} bytes to file {name}")
            except OSError as e:
                self.logger.info(f"Writing file {name} failed with error: {e}")
        else:
            self.logger.info(json.dumps(self.data, indent=2))

    def run(self) -> dict:
        """
        Run functions to process data
        - process_loadbalancer for each namespace and load balancer type
        - process_proxies for each namespace
        - process_origin_pools for each namespace
        - process site labels only if referenced by a load balancer/ origin pool / proxy
        - process site details to get hw info
        :return: processed data
        """

        _processors = dict()
        _processor = None

        for index, processor in enumerate(c.API_PROCESSORS):
            self.logger.info(f"Loading processor <{processor}>...")
            package = load_module(c.PROCESSOR_PACKAGE, processor.lower())
            _processor = getattr(package, processor.capitalize())(session=self.session, api_url=self.api_url, data=self.data, site=self.site, workers=self.workers,
                                                                  logger=self.logger)
            _processors[processor] = _processor
            _processor.run()

        return self.data
