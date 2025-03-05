import concurrent.futures
from abc import abstractmethod
from logging import Logger
from typing import Any

from requests import Response, Session

import lib.const as c


class Base(object):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        self._session = session
        self.api_url = api_url
        self._site = site
        self._urls = list()
        self._data = data
        self._workers = workers
        self._logger = logger
        self.must_break = False

    @property
    def urls(self):
        return self._urls

    @property
    def data(self):
        return self._data

    @property
    def site(self):
        return self._site

    @property
    def session(self):
        return self._session

    @property
    def workers(self):
        return self._workers

    @property
    def logger(self):
        return self._logger

    def get_site_nic_mode(self, site: str = None) -> str | None:
        """
        Check if interface mode key exists in given data. Return site interface mode which is Single NIC or Dual NIC.
        "ingress_gw_ar" and "ingress_egress_ar" not supported. If mode is unknown return None
        :param site: the site name
        :return: return interface mode string
        """

        if "ingress_gw" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
            return "ingress_gw"
        elif "ingress_egress_gw" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
            return "ingress_egress_gw"
        else:
            self.logger.debug(f"Unsupported interface mode for site {site} found")
            return None

    def get_key_from_site_kind(self, site: str = None) -> str | None:
        """
        Returns key name according to site kind/type. Key name is used to create new key below site data structure.
        :param site: site name
        :return: key name
        """

        if self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V1 or self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V2:
            return c.SITE_OBJECT_TYPE_SMS
        else:
            # F5XC_SITE_TYPE_AWS_TGW, F5XC_SITE_TYPE_AWS_VPC, F5XC_SITE_TYPE_AZURE_VNET, F5XC_SITE_TYPE_GCP_VPC
            return c.SITE_OBJECT_TYPE_LEGACY

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

    def execute(self, name: str = None, urls: dict[str, Any] | list[str] = None) -> list | None:
        resp = list()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info(f"Prepare {name} query...")

            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}
            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]
                self.logger.info(f"process {name} get item: {future_to_ds[future]} ...")
                try:
                    data = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % (f"process {name}", _data, exc))
                else:
                    self.logger.info(f"process {name} got item: {future_to_ds[future]} ...")
                    if data:
                        if isinstance(urls, dict):
                            resp.append({"object": urls[future_to_ds[future]], "data": data.json()})
                        elif isinstance(urls, list):
                            #resp.append({"object": urls[future_to_ds[future]], "data": data.json()})
                            resp.append({future_to_ds[future]: data.json()["items"]}) if data and data.json()["items"] else None
                            #print("DATA:", future_to_ds[future])
                            #print("URLS:", urls)

            return resp

    @abstractmethod
    def run(self) -> dict:
        pass
