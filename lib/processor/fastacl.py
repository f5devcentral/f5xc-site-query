import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class FastAcl(Base):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        """
        A class for processing site related firewall fast acl data.
        :param session: current http session
        :param api_url: api url to connect to
        :param data: data structure to add firewall fast acl data to
        :param site: user injected site name to filter for
        :param workers: amount of concurrent threads
        :param logger: log instance for writing / printing log information
        """
        super().__init__(session=session, api_url=api_url, data=data, site=site, workers=workers, logger=logger)

        for namespace in self.data["namespaces"]:
            self.urls.append(self.build_url(c.URI_F5XC_FIREWALL_FAST_ACLS.format(namespace=namespace)))

        self.logger.debug("FIREWALL_FAST_ACLS_URLS: %s", self.urls)

    def run(self) -> dict:
        """
        Add proxies to site if proxy refers to a site. Obtains specific proxy by name.
        :return: structure with proxies information being added
        """

        proxies = self.execute(name="firewall fast acls query", urls=self.urls)

        def process():
            try:
                """
                facl_name = r["metadata"]["name"]
                site_name = site_info[site_type][site_type]['name']
                namespace = r["metadata"]["namespace"]
                if site_name not in self.data[c.OBJECT_TO_KEY_MAP[site_type]].keys():
                    self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name] = dict()
                if "namespaces" not in self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]:
                    self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'] = dict()
                if namespace not in self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'].keys():
                    self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace] = dict()
                if "facls" not in self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace].keys():
                    self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]["facls"] = dict()
                self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]["facls"][facl_name] = dict()
                self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]["facls"][facl_name]['spec'] = dict()
                self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]["facls"][facl_name]['metadata'] = dict()
                self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]["facls"][facl_name]['system_metadata'] = dict()
                self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]['facls'][facl_name]['spec'] = r['spec']
                self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]['facls'][facl_name]['metadata'] = r['metadata']
                self.data[c.OBJECT_TO_KEY_MAP[site_type]][site_name]['namespaces'][namespace]['facls'][facl_name]['system_metadata'] = r['system_metadata']
                self.logger.info(f"process proxies add data: [namespace: {namespace} proxy: {proxy_name} site_type: {site_type} site_name: {site_name}]")
                """
            except Exception as e:
                #self.logger.info("site_type:", site_type)
                self.logger.info("namespace:", r["metadata"]["namespace"])
                self.logger.info("system_metadata:", r['system_metadata'])
                self.logger.info("Exception:", e)


        urls = list()

        for item in proxies:
            for url, proxies in item.items():
                for proxy in proxies:
                    _url = "{}/{}".format(url, proxy['name'])
                    urls.append(_url)

        self.logger.debug(f"process firewall fast acls url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}
            self.must_break = False

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process firewall fast acls get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process firewall fast acls", _data, exc))
                else:
                    self.logger.info(f"process firewall fast acls got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.info(json.dumps(r, indent=2))

        return self.data
