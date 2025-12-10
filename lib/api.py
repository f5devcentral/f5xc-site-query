"""
authors: cklewar
"""

import json
import os
import re
import sys

from collections import OrderedDict
from logging import Logger
from typing import Any, Tuple, List

import jsondiff
import requests
from prettytable import PrettyTable, TableStyle
from requests import Response

import lib.const as c
from lib.loader import load_module
from lib.xlsx import Xlsx


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
    print("target_only_set", target_only_set)

    # Master list of keys
    master_keys = []

    # Regular keys and keys that exist in both
    for key in source_keys:
        master_keys.append(key)

    # Identify and sort Target-Only Keys
    # Note: custom_key_sorter is assumed to exist and sort based on 'node' numbers.
    target_only_keys_sorted = sorted(list(target_only_set), key=custom_key_sorter)
    print("target_only_keys_sorted", target_only_keys_sorted)

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


def join_dict_items(data_dict: dict, separator="\n"):
    """
    Joins all key-value pairs in a dictionary into a single string,
    separated by a specified separator (default is a newline).
    """

    formatted_items = separator.join(f"{key}: {value}" for key, value in data_dict.items())

    return formatted_items


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

    def build_compare_xlsx(self, xlsx_file: str = None, data: str = None, data_source: dict = None, data_target: dict = None):
        """
        Write site comparison to XLSX file
        :param xlsx_file: xlsx output data
        :param data: compared json data
        :param data_source: source site json input data
        :param data_target: target site data json input data
        :return:
        """

        self.logger.info(f"{self.build_compare_xlsx.__name__} started...")

        if data:
            try:
                xlsx = Xlsx(site=self.site, file=xlsx_file, logger=self.logger)
                xlsx.build_compare(data_source=data_source, data_target=data_target)
                xlsx.write()
                self.logger.info(f"{self.build_compare_xlsx.__name__} done.")
            except json.decoder.JSONDecodeError as e:
                self.logger.error(f"Error parsing json data for file {xlsx_file} with error: {e}")
        else:
            self.logger.info("Error data can not be null")

    def build_inventory_xlsx(self, json_file: str = None, xlsx_file: str = None):
        """
        Write site inventory to XLSX file
        :param json_file: json input data
        :param xlsx_file: xlsx output data
        :return:
        """

        self.logger.info(f"{self.build_inventory_xlsx.__name__} started...")
        data = self.read_json_file(json_file)

        if data:
            xlsx = Xlsx(site=self.site, file=xlsx_file, logger=self.logger)
            status = xlsx.build_inventory(data=data)

            if status:
                xlsx.write()
                self.logger.info(f"{self.build_inventory_xlsx.__name__} done.")

    def build_inventory_csv(self, json_file: str = None) -> PrettyTable | None:
        """
        Write site inventory to CSV file
        :param json_file: json input data
        :return: inventory data
        """

        self.logger.info(f"{self.build_inventory_csv.__name__} started...")

        data = self.read_json_file(json_file)
        if data:
            table = PrettyTable()
            table.set_style(TableStyle.SINGLE_BORDER)
            table.field_names = ["No", "Type", "Value", "Subtype1", "SubValue1", "Subtype2", "SubValue2"]
            table.title = "Inventory"
            table.padding_width = 1

            def process():
                record_no = 1
                table.add_row(["{}".format(site), "", "", "", "", "", ""])
                for key, value in site_data.items():
                    if isinstance(value, str):
                        table.add_row([record_no, key, value, "", "", "", ""])
                    elif isinstance(value, int):
                        table.add_row([record_no, key, value, "", "", "", ""])
                    elif isinstance(value, dict):
                        if key in c.CSV_EXPORT_KEYS:
                            if key == "spec":
                                table.add_row([record_no, key, "ce_sw_version", value["volterra_software_version"], "", "", ""])
                            elif key == "spoke":
                                if site_data["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                                    # TODO add azure support
                                    pass
                                elif site_data["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                                    table.add_row([record_no, key, len(value["vpc_list"]), "", "", "", ""])
                            elif key == "nodes":
                                for node, attrs in value.items():
                                    if "interfaces" in attrs:
                                        table.add_row([record_no, "node", node, "interfaces", len(attrs["interfaces"]), "", ""])
                                    if "hw_info" in attrs:
                                        for k, v in c.HW_INFO_ITEMS_TO_PROCESS.items():
                                            if k == "storage":
                                                for s in attrs["hw_info"][k]:
                                                    for item in v:
                                                        if s[item] != 0:
                                                            table.add_row([record_no, "node", node, "hw_info", k, s["name"], s[item]])
                                            else:
                                                for item in v:
                                                    table.add_row([record_no, "node", node, "hw_info", k, item, attrs["hw_info"][k][item]])
                            elif key == "namespaces":
                                for namespace, attrs in value.items():
                                    for ns_item, ns_item_value in attrs.items():
                                        if ns_item == "loadbalancer":
                                            for lb, lb_values in ns_item_value.items():
                                                table.add_row([record_no, key, namespace, ns_item, lb, "",
                                                               '\n'.join(list(lb_values.keys())) if len(lb_values.keys()) > 1 else list(lb_values.keys())[0]])
                                        else:
                                            table.add_row([record_no, key, namespace, ns_item,
                                                           '\n'.join(list(ns_item_value.keys())) if len(ns_item_value.keys()) > 1 else list(ns_item_value.keys())[0], "", ""])
                            else:
                                for name in value:
                                    table.add_row([record_no, key, name, "", "", "", ""])
                    elif isinstance(value, list):
                        if len(value) > 0:
                            table.add_row([record_no, key, format_list_with_newlines(value), "", "", "", ""])
                    record_no += 1

                table.add_divider()

            for site, site_data in data[c.SITES_KEY].items():
                if self.must_break:
                    break
                else:
                    if self.site:
                        if self.site == site:
                            self.must_break = True
                            process()
                            break
                    else:
                        process()

            self.logger.info(f"{self.build_inventory_csv.__name__} -> Done")

            return table
        return None

    def _get_by_path(self, root: dict | list = None, items: list = None, resp: list = None) -> list[str] | None:
        """
        Traverse a nested object by a sequence of path items.
        :param root: the dict or list of values to obtain values from leveraging a path
        :param items: list of items building a path. traverse root according to path and get value
        :param resp: list where processed items will be appended to
        :return: list of items obtained by path
        """

        if items:
            while len(items) > 0:
                item = items[0]
                items.pop(0)

                if isinstance(root, list) and item.isdigit():
                    resp.append(root[int(item)])
                elif isinstance(root, dict):
                    new_root = root.get(int(item)) if item.isdigit() else root.get(item)

                    if new_root:
                        if isinstance(new_root, str):
                            self.logger.debug(f"STRING: {new_root}")
                            resp.append(new_root)
                        elif isinstance(new_root, int):
                            self.logger.debug(f"INT: {new_root}")
                            resp.append(new_root)
                        elif isinstance(new_root, list):
                            self.logger.debug(f"LIST: {new_root}")
                            if all(isinstance(root_item, str) for root_item in new_root):
                                self._get_by_path(new_root, items, resp)
                            else:
                                for root_item in new_root:
                                    self._get_by_path(root_item, items, resp)
                        elif isinstance(root, dict):
                            self.logger.debug(f"DICT: {new_root}")
                            if len(items) == 0:
                                _tmp = root.get(item)
                                if type(_tmp) == list:
                                    # If complete interface definition is missing add list of missing interfaces and not all the sub items.
                                    if item == "interfaces":
                                        for item in _tmp:
                                            if "ethernet_interface" in item:
                                                resp.append(item["ethernet_interface"]["device"])
                                    else:
                                        resp.append(_tmp)
                                elif type(_tmp) == dict:
                                    for item in list(new_root.keys()):
                                        resp.append(item)
                                else:
                                    self.logger.debug(f"DICT: {new_root}")
                                    for item in list(new_root.keys()):
                                        resp.append(item)
                            else:
                                self._get_by_path(new_root, items, resp)
                        else:
                            self.logger.info(f"Unknown key: {type(root)}")
                    else:
                        self.logger.debug(f"new root item: {item}, {type(item)}")
                        self.logger.debug(f"root: {root}")
                        self.logger.debug(f"root.get(): {root.get(item)}")
                else:
                    self.logger.debug(f"Unknown: {root}")

        return resp

    def _get_keys(self, parent_key: str = None, compared: dict = None, resp: list[str] = None, old_site: str = None, data_old: dict = None) -> list[str] | None:
        """
        get_keys will compute list of strings, where each string represents path to key in a dict
        :param parent_key: last key becomes parent key. When func called first time parent key will be None.
        :param compared: holds compared data. With each recursion dictionary will present latest key values
        :param resp: a list of strings. Each string represents a key path later used to access values in site inventory
        :param old_site: old site name
        :param data_old: old site data
        :return: final list of all computed key path strings
        """

        if compared:
            self.logger.debug(f"COMPARED: {compared}")
            keys = list(compared.keys())

            while len(keys) > 0:
                key = keys[0]
                keys.pop(0)

                # skip sms e.g. sms/metadata/labels
                if key not in ["sms"]:
                    if type(key) is jsondiff.symbols.Symbol:
                        if key.label == "delete":
                            self.logger.debug(f"DELETE: {parent_key} -- {key} -- {compared.get(key)}")
                            for item in compared.get(key):
                                if item == "namespaces":
                                    for namespace in data_old[c.SITES_KEY][old_site]['namespaces']:
                                        if "loadbalancer" in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]:
                                            for lb_type in c.F5XC_LOAD_BALANCER_TYPES:
                                                if data_old[c.SITES_KEY][old_site]['namespaces'][namespace]['loadbalancer'].get(lb_type.split("_")[0]):
                                                    resp.append(f"{item}/{namespace}/loadbalancer/{lb_type.split("_")[0]}")
                                                    self.logger.debug(f"APPEND NEW ITEM10: {f"{item}/{namespace}/loadbalancer/{lb_type.split("_")[0]}"}")
                                        if "origin_pools" in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]:
                                            resp.append(f"{item}/{namespace}/origin_pools")
                                            self.logger.debug(f"APPEND NEW ITEM11: {f"{item}/{namespace}/origin_pools"}")
                                        if "proxys" in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]:
                                            resp.append(f"{item}/{namespace}/proxys")
                                            self.logger.debug(f"APPEND NEW ITEM12: {f"{item}/{namespace}/proxys"}")
                                        self.logger.debug(f"APPEND NEW ITEM13: {f"{parent_key}/{item}" if parent_key else f"{item}"}")
                                if item == "loadbalancer":
                                    namespace = parent_key.split("/")[1]
                                    if "loadbalancer" in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]:
                                        for lb_type in c.F5XC_LOAD_BALANCER_TYPES:
                                            if data_old[c.SITES_KEY][old_site]['namespaces'][namespace]['loadbalancer'].get(lb_type.split("_")[0]):
                                                resp.append(f"{parent_key}/{item}/{lb_type.split("_")[0]}")
                                                self.logger.debug(f"APPEND NEW ITEM14: {f"{parent_key}/{item}/{lb_type.split("_")[0]}"}")
                                else:
                                    resp.append(f"{parent_key}/{item}" if parent_key else f"{item}")
                                    self.logger.debug(f"APPEND NEW ITEM16: {f"{parent_key}/{item}" if parent_key else f"{item}"}")
                        elif key.label == "replace":
                            self.logger.debug(f"REPLACE: {parent_key} -- {key} -- {compared.get(key)}")
                            if parent_key == "namespaces":
                                resp.append(f"{parent_key}")
                                for namespace in data_old[c.SITES_KEY][old_site]['namespaces']:
                                    self.logger.debug(f"APPEND NEW ITEM1: {f"{parent_key}/{namespace}"}")
                                    if "loadbalancer" in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]:
                                        for lb_type in c.F5XC_LOAD_BALANCER_TYPES:
                                            if data_old[c.SITES_KEY][old_site]['namespaces'][namespace]['loadbalancer'].get(lb_type.split("_")[0]):
                                                resp.append(f"{parent_key}/{namespace}/loadbalancer/{lb_type.split("_")[0]}")
                                                for lb_name in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]['loadbalancer'][lb_type.split("_")[0]]:
                                                    self.logger.debug(f"APPEND NEW ITEM2: {f"{parent_key}/{namespace}/loadbalancer/{lb_type.split("_")[0]}/{lb_name}"}")
                                    if "origin_pools" in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]:
                                        resp.append(f"{parent_key}/{namespace}/origin_pools")
                                        for op_name in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]['origin_pools']:
                                            self.logger.debug(f"APPEND NEW ITEM3: {f"{parent_key}/{namespace}/origin_pools/{op_name}"}")
                                    if "proxys" in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]:
                                        resp.append(f"{parent_key}/{namespace}/proxys")
                                        for proxy_name in data_old[c.SITES_KEY][old_site]['namespaces'][namespace]['proxys']:
                                            self.logger.debug(f"APPEND NEW ITEM4: {f"{parent_key}/{namespace}/proxys/{proxy_name}"}")
                            else:
                                resp.append(f"{parent_key}" if parent_key else None)
                                self.logger.debug(f"APPEND NEW ITEM5: {f"{parent_key}"}")
                        # elif key.label == "insert":
                        #    self.logger.debug(f"INSERT: {parent_key} -- {key} -- {compared.get(key)}")
                        # resp.append(f"{parent_key}" if parent_key else f"{key}")
                        else:
                            self.logger.debug(f"UNKNOWN KEY: {key}")
                    elif isinstance(compared.get(key), list):
                        # e.g. vsites on target sites
                        self.logger.debug(f"LIST: {parent_key} -- {key} -- {compared.get(key)}")
                        resp.append(f"{parent_key}/{key}" if parent_key else f"{key}")
                        self.logger.debug(f"APPEND NEW ITEM100: {f"{parent_key}/{key}" if parent_key else f"{key}"}")
                    else:
                        if isinstance(compared.get(key), str):
                            if not any(list(map(lambda regex: re.match(regex, key), c.EXCLUDE_COMPARE_ATTRIBUTES))):
                                self.logger.debug(f"STRING: {parent_key} -- {key} -- {compared.get(key)}")
                                resp.append(f"{parent_key}/{key}" if parent_key else f"{key}")
                                self.logger.debug(f"APPEND NEW ITEM101: {f"{parent_key}/{key}" if parent_key else f"{key}"}")
                        elif isinstance(compared.get(key), int):
                            self.logger.debug(f"INT: {parent_key} -- {key} -- {compared.get(key)}")
                            resp.append(f"{parent_key}/{key}" if parent_key else f"{key}")
                            self.logger.debug(f"APPEND NEW ITEM102: {f"{parent_key}/{key}" if parent_key else f"{key}"}")
                        elif isinstance(compared.get(key), dict):
                            self.logger.debug(f"DICT: {key} -- {type(key)} -- {compared.get(key)}")
                            self._get_keys(f"{parent_key}/{key}", compared.get(key), resp, old_site, data_old) if parent_key else self._get_keys(key, compared.get(key), resp,
                                                                                                                                                 old_site, data_old)
                        else:
                            self.logger.debug(f"UNKNOWN KEY: {key} -- {type(compared.get(key))}")

            return resp
        return None

    def compare(self, source: str = None, source_file: str = None, target: str = None, target_file: str = None, data_source: dict = None,
                data_target: dict = None) -> PrettyTable | None:
        """
        Compare takes data of previous run from file and data from current from api and does a comparison of hw_info items
        :param target: target site name to compare with
        :param source: source site name to compare with
        :param target_file: file name data loaded to compare with
        :param source_file: file name data loaded to compare with
        :param data_source: data from source site
        :param data_target: data from target site
        :return: comparison status per hw_info item or False if site is orphaned site or does not exist in data
        """

        self.logger.info(
            f"{self.compare.__name__} started with data from previous run: <{os.path.basename(source_file)}> and data from latest run <{os.path.basename(target_file)}>")
        self.logger.info(f"Compare old site: {source} --> {source_file}")
        self.logger.info(f"Compare new site: {target} --> {target_file}")

        self.logger.debug(f"DATA_OLD: {data_source}")
        self.logger.debug(f"DATA_NEW: {data_target}")

        if data_source and data_target:
            if source in data_source["failed"]:
                self.logger.info(f"Comparing source site <{source}> failed. Error site <{source}> is in <{data_source["failed"][source]}> state")
                return None

            if target in data_target["failed"]:
                self.logger.info(f"Comparing target site <{target}> failed. Error site <{target}> is in <{data_target["failed"][target]}> state")
                return None

            if not target in data_target[c.SITES_KEY]:
                self.logger.info(f"Comparing new site <{target}> not found in file {target_file}.")
                return None

            if not source in data_source[c.SITES_KEY]:
                self.logger.info(f"Comparing new site <{source}> not found in file {source_file}.")
                return None

            # Only support comparison if site type is of same kind or if source site is secure mesh v1 and destination site is secure mesh v2
            legacy_to_smv2 = data_source[c.SITES_KEY][source]['kind'] in [c.F5XC_SITE_TYPE_AWS_VPC, c.F5XC_SITE_TYPE_AWS_TGW, c.F5XC_SITE_TYPE_GCP_VPC,
                                                                          c.F5XC_SITE_TYPE_AZURE_VNET] and data_target[c.SITES_KEY][target]['kind'] == c.F5XC_SITE_TYPE_SMS_V2
            smv1_to_smv2 = data_source[c.SITES_KEY][source]['kind'] == c.F5XC_SITE_TYPE_SMS_V1 and data_target[c.SITES_KEY][target]['kind'] == c.F5XC_SITE_TYPE_SMS_V2

            if legacy_to_smv2 or smv1_to_smv2:

                table = PrettyTable()
                table.set_style(TableStyle.SINGLE_BORDER)
                table.field_names = ["Item", "Source", "Target"]

                if self.site:
                    table.padding_width = 1
                    table.title = self.site

                compare_paths = [
                    "metadata/name",
                    "kind",
                    "metadata/labels",
                    "main_node_count",
                    "worker_node_count",
                    "nodes",
                    "efp",
                    "fpp",
                    "bgp",
                    "smg",
                    "segments",
                    "dc_cluster_group",
                    "vsites",
                    "namespaces",
                    "namespaces/loadbalancer",
                    "namespaces/proxys",
                    "namespaces/origin_pools",
                ]

                source_table_data = list()
                target_table_data = list()

                def recurse(key_path: list, data, table_data):
                    if len(key_path) > 1:
                        recurse(key_path[1:], data[key_path[0]], table_data)
                    else:
                        if key_path[0] == "namespaces":
                            table_data.extend(["add_section_title_namespaces", "namespaces"])
                            table_data.extend([f"namespaces_count", len(data.get(key_path[0]).keys())])
                            table_data.extend([f"namespaces", format_list_with_newlines([namespace for namespace in data.get(key_path[0]).keys()])])
                        elif key_path[0] == "labels":
                            _labels = data.get(key_path[0])
                            for label_key, label_value in _labels.items():
                                if label_key == "ves.io/provider":
                                    table_data.extend(["provider_type", label_value])
                        elif key_path[0] == "nodes":
                            table_data.extend([f"add_section_title_nodes", f"nodes"])
                            for node_name, node_values in data[key_path[0]].items():
                                if node_name in ["node0", "node1", "node2"]:
                                    table_data.extend([f"{node_name}_hostname", node_values["hostname"]])
                                    table_data.extend([f"{node_name}_cpu_count", node_values["hw_info"]["cpu"]["cpus"]])
                                    table_data.extend([f"{node_name}_cpu_model", node_values["hw_info"]["cpu"]["model"]])
                                    table_data.extend([f"{node_name}_memory_size", f"{round(node_values["hw_info"]["memory"]["size_mb"] / 1024)} GB"])
                                    table_data.extend([f"{node_name}_interface_count", len(node_values["interfaces"])])
                                    table_data.extend([f"{node_name}_os_name", node_values["hw_info"]["os"]["name"]])
                                    table_data.extend([f"{node_name}_os_version", node_values["hw_info"]["os"]["version"]])
                                    for index, storage in enumerate(node_values["hw_info"]["storage"]):
                                        table_data.extend([f"{node_name}_storage_{index}", f"{storage["size_gb"]} GB"])
                            # Interfaces
                            if data["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                                for node_name, node_values in data[key_path[0]].items():
                                    node_interfaces = list()
                                    for interface in node_values["interfaces"]:
                                        interface_details = dict()
                                        # table_data.extend([f"add_section_title_{node_name}_interfaces", "node_interfaces"])
                                        if "dedicated_interface" in interface.keys():
                                            interface_details["is_primary"] = "true" if "is_primary" in interface["dedicated_interface"].keys() else "false"
                                            interface_details["device_name"] = interface["dedicated_interface"]["device"]
                                            interface_details["description"] = interface["description"] if interface["description"] != "" else "None"
                                            interface_details["interface_type"] = "dedicated_interface"
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_is_primary", interface_details["is_primary"]])
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_description", interface_details["description"]])
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_type", interface_details["interface_type"]])
                                            node_interfaces.append(interface_details["device_name"])
                                        if "ethernet_interface" in interface.keys():
                                            interface_details["mtu"] = interface["ethernet_interface"]["mtu"]
                                            interface_details["is_primary"] = True if "is_primary" in interface["ethernet_interface"].keys() else False
                                            interface_details["dhcp_server"] = "true" if "dhcp_server" in interface.keys() else "false"
                                            interface_details["device_name"] = interface["ethernet_interface"]["device"]
                                            interface_details["description"] = interface["description"] if interface["description"] != "" else "None"
                                            if "dhcp_server" in interface["ethernet_interface"].keys():
                                                network_prefixes = list()
                                                for network in interface["ethernet_interface"]["dhcp_server"]["dhcp_networks"]:
                                                    network_prefixes.append(network["network_prefix"])
                                                interface_details["dhcp_networks"] = ",".join(network_prefixes) if network_prefixes else "None"
                                            interface_details["interface_type"] = "ethernet_interface"
                                            interface_details["segment_network"] = interface["ethernet_interface"]["segment_network"]["name"] if "segment_network" in interface[
                                                "ethernet_interface"].keys() else "None"
                                            node_interfaces.append(interface_details["device_name"])

                                        # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_type", interface_details["interface_type"]])
                                        # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_description", interface_details["description"]])
                                        # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_is_primary", interface_details["is_primary"]])
                                        # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_server", interface_details["dhcp_server"]])
                                        # if "dhcp_networks" in interface_details.keys():
                                        #     table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_networks", interface_details["dhcp_networks"]])
                                    table_data.extend([f"{node_name}_interfaces", format_list_with_newlines(node_interfaces)])
                            elif data["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                                for node_name, node_values in data[key_path[0]].items():
                                    node_interfaces = list()
                                    for interface in node_values["interfaces"]:
                                        interface_details = dict()
                                        interface_details["mtu"] = interface["mtu"] if "mtu" in interface else "None"
                                        interface_details["is_primary"] = interface["is_primary"] if "is_primary" in interface else "None"
                                        interface_details["description"] = interface["description"] if interface["description"] != "" else "None"
                                        interface_details["is_management"] = interface["is_management"] if "is_management" in interface else "None"
                                        interface_details["site_local_network"] = "True" if "site_local_network" in interface["network_option"] else "None"
                                        interface_details["site_local_inside_network"] = "True" if "site_local_inside_network" in interface["network_option"] else "None"
                                        interface_details["dhcp_client"] = "True" if "dhcp_client" in interface else "False"
                                        interface_details["dhcp_server"] = "true" if "dhcp_server" in interface.keys() else "false"
                                        interface_details["segment_network"] = interface["network_option"]["segment_network"]["name"] if "segment_network" in interface[
                                            "network_option"].keys() else "None"
                                        if "dhcp_server" in interface.keys():
                                            network_prefixes = list()
                                            for network in interface["dhcp_server"]["dhcp_networks"]:
                                                network_prefixes.append(network["network_prefix"])
                                            interface_details["dhcp_networks"] = ",".join(network_prefixes) if network_prefixes else "None"
                                        if "ethernet_interface" in interface.keys():
                                            interface_details["device_name"] = interface["ethernet_interface"]["device"]
                                            interface_details["interface_type"] = "ethernet_interface"
                                            interface_details["mac"] = interface["ethernet_interface"]["mac"] if "ethernet_interface" in interface[
                                                "ethernet_interface"].keys() else "None"
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_type", interface_details["interface_type"]])
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_description", interface_details["description"]])
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_is_primary", interface_details["is_primary"]])
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_site_local_network", interface_details["site_local_network"]])
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_site_local_inside_network", interface_details["site_local_inside_network"]])
                                            # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_server", interface_details["dhcp_server"]])
                                            # if "dhcp_networks" in interface_details.keys():
                                            #    table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_networks", interface_details["dhcp_networks"]])
                                        node_interfaces.append(interface["name"])
                                    table_data.extend([f"{node_name}_interfaces", format_list_with_newlines(node_interfaces)])
                            else:
                                # Legacy sites
                                for node_name, node_values in data[key_path[0]].items():
                                    node_interfaces = list()
                                    for interface_name, interface_attrs in node_values["interfaces"].items():
                                        interface_details = dict()
                                        #interface_details["device_name"] = interface_name
                                        #interface_details["ipv4"] = interface_attrs["subnet_param"]["ipv4"] if "subnet_param" in interface_attrs else None
                                        #interface_details["ipv6"] = interface_attrs["subnet_param"]["ipv6"] if "subnet_param" in interface_attrs else None
                                        #interface_details["existing_subnet_id"] = interface_attrs["existing_subnet_id"] if "existing_subnet_id" in interface_attrs else None
                                        #_interface = [f"Node0", f"{interface_details["device_name"]}", join_dict_items(interface_details)]
                                        node_interfaces.append(interface_name)
                                    table_data.extend([f"{node_name}_interfaces", format_list_with_newlines(node_interfaces)])
                        elif key_path[0] == "vsites":
                            table_data.extend(["add_section_title_virtual_sites", "virtual_sites"])
                            table_data.extend([f"virtual_sites_count", len(data.get(key_path[0]) if data.get(key_path[0]) is not None else [])])
                            table_data.extend([f"virtual_sites", format_list_with_newlines(data.get(key_path[0]))])
                        elif key_path[0] == "origin_pools":
                            origin_pool_count = 0
                            for namespace, values in data.items():
                                table_data.extend(["add_section_title_op", "origin_pools"])
                                for item, item_values in values.items():
                                    if item == "origin_pools":
                                        origin_pools = values.get(key_path[0])
                                        origin_pool_count = origin_pool_count + len(origin_pools.keys())
                                        table_data.extend([f"origin_pool_count", origin_pool_count])
                                        table_data.extend([f"{namespace}[origin_pools]", format_list_with_newlines(list(origin_pools.keys()))])
                        elif key_path[0] == "loadbalancer":
                            load_balancer_count = 0
                            for namespace, values in data.items():
                                table_data.extend(["add_section_title_lb", "load_balancer"])
                                for item, item_values in values.items():
                                    if item == "loadbalancer":
                                        for lb_type, load_balancer in item_values.items():
                                            load_balancer_count = load_balancer_count + len(load_balancer.keys())
                                            table_data.extend([f"load_balancer_count", load_balancer_count])
                                            table_data.extend([f"{namespace}[load_balancer][{lb_type}]", format_list_with_newlines(list(load_balancer.keys()))])
                        elif key_path[0] == "proxys":
                            proxys_count = 0
                            for namespace, values in data.items():
                                table_data.extend(["add_section_title_proxys", "proxys"])
                                for item, item_values in values.items():
                                    if item == "proxys":
                                        proxys_count = proxys_count + len(item_values.keys())
                                        table_data.extend([f"proxys_count", proxys_count])
                                        table_data.extend([f"{namespace}[proxys]", format_list_with_newlines(list(item_values.keys()))])
                        elif key_path[0] == "dc_cluster_group":
                            table_data.extend(["add_section_title_dc_cluster_group", "dc_cluster_group"])
                            table_data.extend([f"dc_cluster_group", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                        elif key_path[0] == "smg":
                            table_data.extend(["add_section_title_smg", "site_mesh_group"])
                            table_data.extend([f"smg_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                            table_data.extend([f"smg", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                        elif key_path[0] == "efp":
                            table_data.extend(["add_section_title_efp", "enhanced_firewall_policy"])
                            table_data.extend([f"efp_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                            table_data.extend([f"efp", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                        elif key_path[0] == "fpp":
                            table_data.extend(["add_section_title_fpp", "forward_proxy_policy"])
                            table_data.extend([f"fpp_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                            table_data.extend([f"fpp", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                        elif key_path[0] == "bgp":
                            table_data.extend(["add_section_title_bgp", "bgp"])
                            table_data.extend([f"bgp_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                            table_data.extend([f"bgp", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                        elif key_path[0] == "segments":
                            table_data.extend(["add_section_title_segments", "segments"])
                            table_data.extend([f"segments_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                            table_data.extend([f"segments", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                        else:
                            table_data.extend([key_path[0], data.get(key_path[0])])

                for allowed_path in compare_paths:
                    p = allowed_path.split("/")
                    recurse(p, data_source[c.SITES_KEY][source], source_table_data)
                    recurse(p, data_target[c.SITES_KEY][target], target_table_data)

                # Convert flat lists into ordered Dictionaries (using OrderedDict for robustness across Python versions)
                # The slicing [::2] gets keys, [1::2] gets values. zip combines them into (key, value) pairs.
                source_dict = OrderedDict(zip(source_table_data[0::2], source_table_data[1::2]))
                target_dict = OrderedDict(zip(target_table_data[0::2], target_table_data[1::2]))

                self.logger.debug(source_dict)
                self.logger.debug(target_dict)

                # Build the final result list using the unified keys
                placeholder = 'N/A'

                # Master Key Liste generieren
                source_keys = list(source_dict.keys())
                target_keys = list(target_dict.keys())
                final_master_keys = build_master_key_list(source_keys, target_keys)

                for key in final_master_keys:
                    val1 = source_dict.get(key, placeholder)
                    val2 = target_dict.get(key, placeholder)

                    if key.startswith("add_section_title_"):
                        table.add_divider()
                    else:
                        table.add_row([key, val1, val2])

                return table

        return None

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
