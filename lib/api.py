"""
authors: cklewar
"""

import json
import os
import re
import sys
from logging import Logger
from typing import Any

import jsondiff
import requests
from jsondiff import diff
from prettytable import PrettyTable, TableStyle
from requests import Response

import lib.const as c
from lib.xlsx import Xlsx
from lib.loader import load_module


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
                    self.logger.info(f"{len(data[c.SITES_KEY])} {c.SITES_KEY if len(data[c.SITES_KEY]) > 1 else c.SITES_KEY} and {len(data[c.VIRTUAL_SITES_KEY])} virtual {c.SITES_KEY if len(data[c.VIRTUAL_SITES_KEY]) > 1 else c.SITES_KEY} read from {name}")
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
                    fd.write(json.dumps(self.data, indent=2))
                    self.logger.info(f"{len(self.data[c.SITES_KEY])} {'sites' if len(self.data[c.SITES_KEY]) > 1 else c.SITES_KEY} and {len(self.data[c.VIRTUAL_SITES_KEY])} virtual {'sites' if len(self.data[c.VIRTUAL_SITES_KEY]) > 1 else c.SITES_KEY} written to {name}")
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
            xlsx.build_inventory(data=data)
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
                                                table.add_row([record_no, key, namespace, ns_item, lb, "", '\n'.join(list(lb_values.keys())) if len(lb_values.keys()) > 1 else list(lb_values.keys())[0]])
                                        else:
                                            table.add_row([record_no, key, namespace, ns_item, '\n'.join(list(ns_item_value.keys())) if len(ns_item_value.keys()) > 1 else list(ns_item_value.keys())[0], "", ""])
                            else:
                                for name in value:
                                    table.add_row([record_no, key, name, "", "", "", ""])
                    elif isinstance(value, list):
                        if len(value) > 0:
                            table.add_row([record_no, key, value, "", "", "", ""])
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
                                    self.logger.debug(f"APPEND NEW ITEM15: {f"{parent_key}/{item}" if parent_key else f"{item}"}")
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
                        #elif key.label == "insert":
                        #    self.logger.info(f"INSERT: {parent_key} -- {key} -- {compared.get(key)}")
                            #resp.append(f"{parent_key}" if parent_key else f"{key}")
                        else:
                            self.logger.debug(f"UNKNOWN KEY: {key}")
                    elif isinstance(compared.get(key), list):
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
                            self._get_keys(f"{parent_key}/{key}", compared.get(key), resp, old_site, data_old) if parent_key else self._get_keys(key, compared.get(key), resp, old_site, data_old)
                        else:
                            self.logger.debug(f"UNKNOWN KEY: {key} -- {type(compared.get(key))}")

            return resp
        return None

    def compare(self, source: str = None, source_file: str = None, target: str = None, target_file: str = None, data_source: dict = None, data_target: dict = None) -> PrettyTable | None:
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

        self.logger.info(f"{self.compare.__name__} started with data from previous run: <{os.path.basename(source_file)}> and data from latest run <{os.path.basename(target_file)}>")
        self.logger.info(f"Compare old site: {source} --> {source_file}")
        self.logger.info(f"Compare new site: {target} --> {target_file}")

        self.logger.debug(f"DATA_OLD: {data_source}")
        self.logger.debug(f"DATA_NEW: {data_target}")

        if data_source and data_target:
            # Only support comparison if site type is of same kind or if source site is secure mesh v1 and destination site is secure mesh v2
            if not target in data_target[c.SITES_KEY]:
                self.logger.info(f"Comparing new site <{target}> not found in file {target_file}.")
                return None

            if not source in data_source[c.SITES_KEY]:
                self.logger.info(f"Comparing new site <{source}> not found in file {source_file}.")
                return None

            legacy_to_smv2 = data_source[c.SITES_KEY][source]['kind'] in [c.F5XC_SITE_TYPE_AWS_VPC, c.F5XC_SITE_TYPE_AWS_TGW, c.F5XC_SITE_TYPE_GCP_VPC, c.F5XC_SITE_TYPE_AZURE_VNET] and data_target[c.SITES_KEY][target]['kind'] == c.F5XC_SITE_TYPE_SMS_V2
            smv1_to_smv2 = data_source[c.SITES_KEY][source]['kind'] == c.F5XC_SITE_TYPE_SMS_V1 and data_target[c.SITES_KEY][target]['kind'] == c.F5XC_SITE_TYPE_SMS_V2

            if legacy_to_smv2 or smv1_to_smv2:
                compared = diff(data_source[c.SITES_KEY][source], data_target[c.SITES_KEY][target], syntax="compact")
                r = []
                # build list of key paths
                dict_keys = self._get_keys(None, compared, r, source, data_source)

                table = PrettyTable()
                table.set_style(TableStyle.SINGLE_BORDER)
                table.field_names = ["path", "values"]

                if self.site:
                    table.padding_width = 1
                    table.title = self.site

                for k in dict_keys:
                    response = list()
                    # get list of items to be added as table row data
                    values_from_path = self._get_by_path(data_source[c.SITES_KEY][source], k.split("/"), response)

                    if values_from_path:
                        if not any(list(map(lambda regex: re.match(regex, k), c.EXCLUDE_COMPARE_ATTRIBUTES))):
                            if re.match(c.COMPARE_REGEX_HW_INFO_CPU_FLAGS, k):
                                start = 0
                                item_counter = 0
                                values_from_path_as_list = values_from_path[0].split(" ")

                                for i in range(len(values_from_path_as_list)):
                                    if item_counter == 15:
                                        table.add_row([k, values_from_path_as_list[start:i]])
                                        start = i
                                        item_counter = 0
                                    item_counter += 1
                                table.add_divider()
                            elif re.match(c.COMPARE_REGEX_HW_INFO_USB, k):
                                for item in values_from_path:
                                    for item1 in item:
                                        for k1,v in item1.items():
                                            table.add_row([k, {k1: v}])
                                table.add_divider()
                            else:
                                table.add_row([k, values_from_path[0] if len(values_from_path) == 1 else values_from_path])
                                table.add_divider()

                return table
            else:
                self.logger.info(f"Comparing new site <{target}> with old site <{source}> not supported since not of same kind.")
                return None

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
            _processor = getattr(package, processor.capitalize())(session=self.session, api_url=self.api_url, data=self.data, site=self.site, workers=self.workers, logger=self.logger)
            _processors[processor] = _processor
            _processor.run()

        return self.data
