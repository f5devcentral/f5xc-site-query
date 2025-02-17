"""
authors: cklewar
"""

import csv
import json
import os
import sys
from logging import Logger

import requests
from requests import Response

import lib.const as c
from lib.info import HwInfo
from lib.processor.bgp import Bgp
from lib.processor.site import Site


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
    process_sites()
        get and process sites
    process_site_details()
        get site details
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
        self._data = {key: dict() for key in c.F5XC_SITE_TYPES}
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
                json_items = response.json()
                self.data['namespaces'] = [item['name'] for item in json_items['items']]
                self.logger.info(f"Processing {len(self.data['namespaces'])} available namespaces")
            else:
                sys.exit(1)

        else:
            # check api url and validate given namespace
            response = self.get(self.build_url(f"{c.URI_F5XC_NAMESPACE}/{namespace}"))

            if response:
                self.logger.debug(json.dumps(response.json(), indent=2))
                self.data['namespaces'] = [namespace]
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
                    self.logger.info(f"{len(self.data['site'])} {'sites' if len(self.data['site']) > 1 else 'site'} and {len(self.data['virtual_site'])} virtual {'sites' if len(self.data['virtual_site']) > 1 else 'site'} written to {name}")
            except OSError as e:
                self.logger.info(f"Writing file {name} failed with error: {e}")
        else:
            self.logger.info(json.dumps(self.data, indent=2))

    def write_csv_file(self, name: str = None, data: dict[str, bool] = None):
        """
        Flatten JSON data. Write flattened data to CSV
        :param name:
        :param data:
        :return:
        """

        with open(name, 'w', newline='') as fd:
            fieldnames = ["site"] + [k for k in data.keys()]
            writer = csv.DictWriter(fd, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerow({'site': self.site, 'os': data['os'], 'cpu': data['cpu'], 'memory': data['memory'], 'storage': data['storage'], 'network': data['network']})

    def write_csv_inventory(self, json_file: str = None, csv_file: str = None):
        """
        Write site inventory to CSV file
        :param json_file: json input data
        :param csv_file: output csv file
        :return:
        """

        self.logger.info(f"{self.write_csv_inventory.__name__} started...")

        def process():
            for k, v in attrs['namespaces'].items():
                for k1, v1 in v.items():
                    for k2, v2 in v1.items():
                        if k1 == "loadbalancer":
                            for k3, v3 in v2.items():
                                if "spec" in v3.keys():
                                    if "advertise_custom" in v3['spec'].keys():
                                        _row = {"type": k1, "subtype_a": k2, "subtype_b": 'Advertise Policy Custom', "object_name": k3}
                                        rows.append(_row)

                        elif k1 == "origin_pools":
                            _row = {"type": k1, "subtype_a": "N/A", "subtype_b": 'N/A', "object_name": k2}
                            rows.append(_row)

                        elif k1 == "proxys":
                            if "spec" in v2.keys():
                                proxy_type = "dynamic_proxy" if v2['spec'].get("dynamic_proxy") else "http_proxy" if v2['spec'].get("http_proxy") else "unknown"
                                advertise_where_types = list()

                                for item in v2['spec']['site_virtual_sites']['advertise_where']:
                                    advertise_where_type = 'site' if item.get('site') else 'virtual_site'
                                    advertise_where_types.append(advertise_where_type)

                                _row = {"type": "proxy", "subtype_a": proxy_type, "subtype_b": f"Advertise Policies [{'/'.join(advertise_where_types).capitalize()}]", "object_name": k2}
                                rows.append(_row)
                        else:
                            print(f"unknown type {k1}")
            _row = {"type": 20 * "#", "subtype_a": 20 * "#", "subtype_b": 40 * "#", "object_name": 40 * "#"}
            rows.append(_row)

        fieldnames = ["type", "subtype_a", "subtype_b", "object_name"]
        data = self.read_json_file(json_file)
        rows = list()

        for site, attrs in data['site'].items():
            row = {"type": "site", "subtype_a": "N/A", "subtype_b": "N/A", "object_name": site}
            rows.append(row)
            process()

        for site, attrs in data['virtual_site'].items():
            row = {"type": "virtual_site", "subtype_a": "N/A", "subtype_b": "N/A", "object_name": site}
            rows.append(row)
            process()

        with open(csv_file, 'w', newline='') as fd:
            writer = csv.DictWriter(fd, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                writer.writerow(row)

        self.logger.info(f"{self.write_csv_inventory.__name__} -> Done")

    def read_json_file(self, name: str = None) -> dict:
        try:
            with open(name, 'r') as fd:
                data = json.load(fp=fd)
                self.logger.info(f"{len(data['site'])} {'sites' if len(data['site']) > 1 else 'site'} and {len(data['virtual_site'])} virtual {'sites' if len(data['virtual_site']) > 1 else 'site'} read from {name}")
                return data
        except OSError as e:
            self.logger.info(f"Reading file {name} failed with error: {e}")

    def run(self) -> dict:
        """
        Run functions to process data
            - process_loadbalancer for each namespace and load balancer type
            - process_proxies for each namespace
            - process_origin_pools for each namespace
            - process site labels only if referenced by a load balancer/ origin pool / proxy
            - process site details to get hw info
        :return:
        """

        lb_urls = list()
        proxy_urls = list()
        origin_pool_urls = list()

        for namespace in self.data["namespaces"]:
            proxy_urls.append(self.build_url(c.URI_F5XC_PROXIES.format(namespace=namespace)))
            origin_pool_urls.append(self.build_url(c.URI_F5XC_ORIGIN_POOLS.format(namespace=namespace)))

            for lb_type in c.F5XC_LOAD_BALANCER_TYPES:
                lb_urls.append(self.build_url(c.URI_F5XC_LOAD_BALANCER.format(namespace=namespace, lb_type=lb_type)))

        self.logger.debug("LB_URLS: %s", lb_urls)
        self.logger.debug("PROXY_URLS: %s", proxy_urls)
        self.logger.debug("ORIGIN_POOL_URLS: %s", origin_pool_urls)

        #lb = Lb(session=self.session, api_url=self.api_url, urls=lb_urls, data=self.data, site=self.site, workers=self.workers, logger=self.logger)
        #lb.run()

        """
        proxy = Proxy(session=self.session, api_url=self.api_url, urls=lb_urls, data=self.data, site=self.site, workers=self.workers, logger=self.logger)
        proxy.run()
        """

        #origin_pool = OriginPool(session=self.session, api_url=self.api_url, urls=lb_urls, data=self.data, site=self.site, workers=self.workers, logger=self.logger)
        #origin_pool.run()

        """
        site_mesh_group = SiteMeshGroup(session=self.session, api_url=self.api_url, urls=lb_urls, data=self.data, site=self.site, workers=self.workers, logger=self.logger)
        site_mesh_group.run()
        """

        bgp = Bgp(session=self.session, api_url=self.api_url, urls=lb_urls, data=self.data, site=self.site, workers=self.workers, logger=self.logger)
        bgp.run()

        site = Site(session=self.session, api_url=self.api_url, urls=lb_urls, data=self.data, site=self.site, workers=self.workers, logger=self.logger)
        site.run()

        return self.data

    def compare(self, file: str = None) -> dict[str, bool] | bool:
        """
        Compare takes data of previous run from file and data from current from api and does a comparison of hw_info items
        :param file: file name data loaded to compare with
        :return: comparison status per hw_info item or False if site is orphaned site or does not exist in data
        """

        self.logger.info(f"{self.compare.__name__} started with data from {os.path.basename(file)} and current api run...")
        data = self.read_json_file(file)

        if self.site in self.data['orphaned_sites'] or self.site in data['orphaned_sites']:
            self.logger.info(f"{self.compare.__name__} site {self.site} cannot be compared since orphaned site...")
            return False

        elif self.site not in self.data['site'] or self.site not in data['site']:
            self.logger.info(f"{self.compare.__name__} site {self.site} cannot be compared. Site not found  in existing data...")
            return False

        else:
            hw_info_a = HwInfo(**data['site'][self.site]['hw_info'])
            hw_info_b = HwInfo(**self.data['site'][self.site]['hw_info'])
            self.logger.info(f"{self.compare.__name__} done with results: {hw_info_a == hw_info_b}")

            return hw_info_a == hw_info_b
