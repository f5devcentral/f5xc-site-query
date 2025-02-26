"""
authors: cklewar
"""

import json
import os
import sys
from logging import Logger
from typing import Any

import jsondiff
import requests
from jsondiff import diff
from prettytable import PrettyTable, TableStyle
from requests import Response

import lib.const as c
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

    def __init__(self, _logger: Logger = None, api_url: str = None, api_token: str = None, namespace: str = None, site: str = None, workers: int = 10):
        """
        Initialize API object. Stores session state and allows to run data processing methods.

        :param api_url: F5XC API URL
        :param api_token: F5XC API token
        :param namespace: F5XC namespace
        :param site: F5XC site
        :param workers: Maximum number of workers for concurrent processing
        """

        self._logger = _logger
        self._data = dict()
        for key in c.F5XC_SITE_TYPES:
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
            self.logger.debug("get failed for {} with {}".format(url, r.status_code))
            return False

        return r if r else False

    def read_json_file(self, name: str = None) -> Any | None:
        try:
            with open(name, 'r') as fd:
                data = json.load(fp=fd)
                self.logger.info(f"{len(data['site'])} {'sites' if len(data['site']) > 1 else 'site'} and {len(data['virtual_site'])} virtual {'sites' if len(data['virtual_site']) > 1 else 'site'} read from {name}")
                return data
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
                    self.logger.info(f"{len(self.data['site'])} {'sites' if len(self.data['site']) > 1 else 'site'} and {len(self.data['virtual_site'])} virtual {'sites' if len(self.data['virtual_site']) > 1 else 'site'} written to {name}")
            except OSError as e:
                self.logger.info(f"Writing file {name} failed with error: {e}")
        else:
            self.logger.info(json.dumps(self.data, indent=2))

    def write_string_file(self, name: str = None, data: str = None):
        """
        Write string to file
        :param name:
        :param data:
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

    def build_inventory(self, json_file: str = None) -> PrettyTable | None:
        """
        Write site inventory to CSV file
        :param json_file: json input data
        :return: inventory data
        """

        self.logger.info(f"{self.build_inventory.__name__} started...")

        data = self.read_json_file(json_file)
        table = PrettyTable()
        table.set_style(TableStyle.SINGLE_BORDER)
        table.field_names = ["No", "Type", "Value", "Subtype", "SubValue"]
        table.title = "Inventory"
        table.padding_width = 1

        def process():
            record_no = 1
            table.add_row(["{}".format(site), "", "", "", ""])
            for key, value in site_data.items():
                if isinstance(value, str):
                    table.add_row([record_no, key, value, "", ""])
                elif isinstance(value, int):
                    table.add_row([record_no, key, value, "", ""])
                elif isinstance(value, dict):
                    if key in c.CSV_EXPORT_KEYS:
                        if key == "spoke":
                            if site_data["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                                # TODO add azure support
                                pass
                            elif site_data["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                                table.add_row([record_no, key, len(value["vpc_list"]), "", ""])
                        elif key == "nodes":
                            for node, attrs in value.items():
                                # Skip SMv2 since no interface information available. process_node_interfaces() in site needs to be extended to support this
                                if site_data["kind"] != c.F5XC_SITE_TYPE_SMS_V2:
                                    table.add_row([record_no, "node", node, "interfaces", len(attrs["interfaces"])])
                                    if "hw_info" in attrs:
                                        table.add_row([record_no, "node", node, "os", attrs["hw_info"]["os"]["vendor"]])
                                    else:
                                        pass
                                        #print(site, attrs)
                        elif key == "namespaces":
                            for namespace, attrs in value.items():
                                for ns_item, ns_item_value  in attrs.items():
                                    table.add_row([record_no, key, namespace, ns_item, list(ns_item_value.keys()) if len(ns_item_value.keys()) > 1 else list(ns_item_value.keys())[0]])
                        else:
                            for name in value:
                                table.add_row([record_no, key, name, "", ""])
                elif isinstance(value, list):
                    if len(value) > 0:
                        table.add_row([record_no, key, value, "", ""])
                record_no += 1

            table.add_divider()

        for site, site_data in data['site'].items():
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

        self.logger.info(f"{self.build_inventory.__name__} -> Done")

        return table

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

    def compare(self, old_file: str = None, new_file: str = None) -> PrettyTable | None:
        """
        Compare takes data of previous run from file and data from current from api and does a comparison of hw_info items
        :param new_file: file name data loaded to compare with
        :param old_file: file name data loaded to compare with
        :return: comparison status per hw_info item or False if site is orphaned site or does not exist in data
        """

        self.logger.info(f"{self.compare.__name__} started with data from previous run: <{os.path.basename(old_file)}> and data from latest run <{os.path.basename(new_file)}>")
        data_old = self.read_json_file(old_file)
        data_new = self.read_json_file(new_file)

        compared = diff(data_old['site'][self.site], data_new['site'][self.site], syntax="compact")

        def generic_items(dict_or_list):
            if isinstance(dict_or_list, dict):
                return dict_or_list.items()
            if isinstance(dict_or_list, list):
                return enumerate(dict_or_list)

        def get_by_path(root: dict = None, items: list = None, resp: list = None):
            """
            Access a nested object in root by item sequence.
            :param root:
            :param items:
            :param resp:
            :return:
            """

            if items:
                while len(items) > 0:
                    item = items[0]
                    items.pop(0)

                    if isinstance(root, list):
                        self.logger.debug(f"LIST: {root}")
                    elif isinstance(root, dict):
                        new_root = root.get(int(item)) if item.isdigit() else root.get(item)

                        if new_root:
                            if isinstance(new_root, str):
                                self.logger.debug(f"STRING: {new_root}")
                                resp.append(new_root)
                            elif isinstance(new_root, int):
                                self.logger.debug(f"INT: {new_root}")
                                resp.append(new_root)
                            elif isinstance(root, list):
                                self.logger.debug(f"LIST: {new_root}")
                            elif isinstance(root, dict):
                                self.logger.debug(f"DICT: {new_root}")
                                get_by_path(new_root, items, resp)
                            else:
                                self.logger.debug(f"Unknown: {type(root)}")
                        else:
                            self.logger.debug(f"new root item: {item}, {type(item)}")
                            self.logger.debug(f"root: {root}")
                            self.logger.debug(f"root.get(): {root.get(0)}")
                    else:
                        self.logger.debug(f"Unknown: {root}")

            return resp

        def get_keys(parent_key, dictionary):
            """

            :param parent_key:
            :param dictionary:
            :return:
            """
            r = []

            for key, _v in generic_items(dictionary):
                if type(key) is jsondiff.symbols.Symbol:
                    get_keys(parent_key, _v)
                else:
                    if type(_v) is dict:
                        new_keys = get_keys(key, _v)
                        for inner_key in new_keys:
                            r.append(f'{key}/{inner_key}')
                    elif type(_v) is list:
                        new_keys = get_keys(key, _v)
                        for inner_key in new_keys:
                            r.append(f'{key}/{_v[inner_key]}')
                    else:
                        r.append(key)

            return r

        def get_keys_schema(parent_key, dictionary, r):
            """

            :param parent_key:
            :param dictionary:
            :param r:
            :return:
            """

            for key, _v in generic_items(dictionary):
                if type(key) is jsondiff.symbols.Symbol:
                    if isinstance(_v, list):
                        for item in _v:
                            r.append((parent_key, item))
                elif isinstance(_v, dict):
                    get_keys_schema(key, _v, r)
                elif isinstance(_v, list):
                    get_keys_schema(key, _v, r)
                    r.append((key, _v))
                else:
                    self.logger.debug(f"unknown item: {key}, {type(_v)}")
            return r

        result = []

        k1 = get_keys(None, compared)
        k2 = get_keys_schema(None, compared, result)

        table = PrettyTable()
        table.set_style(TableStyle.SINGLE_BORDER)
        table.field_names = ["item", "diff"]

        if self.site:
            table.padding_width = 1
            table.title = self.site

        for k in k1:
            response = list()
            r1 = get_by_path(compared, [k for k in k.split("/")], response)
            table.add_row([k, r1[0]])
            table.add_divider()

        for k in k2:
            table.add_row([k[0], k[1]])
            table.add_divider()

        return table
