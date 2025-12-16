import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base

__DEPENDENCIES__ = ["site"]


class Proxy(Base):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        """
        A class for processing site related proxy data.
        :param session: current http session
        :param api_url: api url to connect to
        :param data: data structure to add proxy data to
        :param site: user injected site name to filter for
        :param workers: amount of concurrent threads
        :param logger: log instance for writing / printing log information
        """
        super().__init__(session=session, api_url=api_url, data=data, site=site, workers=workers, logger=logger)

        for namespace in self.data["namespaces"]:
            self.urls.append(self.build_url(c.URI_F5XC_PROXIES.format(namespace=namespace)))

        self.logger.debug("PROXY_URLS: %s", self.urls)

    def run(self) -> dict:
        """
        Add proxies to site if proxy refers to a site. Obtains specific proxy by name.
        :return: structure with proxies information being added
        """
        proxies = self.execute(name="proxies query", urls=self.urls)

        def process():
            try:
                proxy_name = r["metadata"]["name"]
                namespace = r["metadata"]["namespace"]
                if site_name not in self.data[c.SITES_KEY].keys():
                    self.data[c.SITES_KEY][site_name] = dict()
                if "namespaces" not in self.data[c.SITES_KEY][site_name]:
                    self.data[c.SITES_KEY][site_name]['namespaces'] = dict()
                if namespace not in self.data[c.SITES_KEY][site_name]['namespaces'].keys():
                    self.data[c.SITES_KEY][site_name]['namespaces'][namespace] = dict()
                if "proxys" not in self.data[c.SITES_KEY][site_name]['namespaces'][namespace].keys():
                    self.data[c.SITES_KEY][site_name]['namespaces'][namespace]["proxys"] = dict()

                self.data[c.SITES_KEY][site_name]['namespaces'][namespace]["proxys"][proxy_name] = dict()
                self.data[c.SITES_KEY][site_name]['namespaces'][namespace]["proxys"][proxy_name]['spec'] = dict()
                self.data[c.SITES_KEY][site_name]['namespaces'][namespace]["proxys"][proxy_name]['metadata'] = dict()
                self.data[c.SITES_KEY][site_name]['namespaces'][namespace]["proxys"][proxy_name]['system_metadata'] = dict()
                self.data[c.SITES_KEY][site_name]['namespaces'][namespace]['proxys'][proxy_name]['spec'] = r['spec']
                self.data[c.SITES_KEY][site_name]['namespaces'][namespace]['proxys'][proxy_name]['metadata'] = r['metadata']
                self.data[c.SITES_KEY][site_name]['namespaces'][namespace]['proxys'][proxy_name]['system_metadata'] = r['system_metadata']
                self.logger.info(f"process proxies add data: [namespace: {namespace} proxy: {proxy_name} site_type: {site_type} site_name: {site_name}]")
            except Exception as e:
                self.logger.info("site_type:", site_type)
                self.logger.info("namespace:", r["metadata"]["namespace"])
                self.logger.info("system_metadata:", r['system_metadata'])
                self.logger.info("Exception:", e)

        urls = list()

        for item in proxies:
            for url, proxies in item.items():
                for proxy in proxies:
                    _url = "{}/{}".format(url, proxy['name'])
                    urls.append(_url)

        self.logger.debug(f"process proxies url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}
            self.must_break = False

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process proxies get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process proxies", _data, exc))
                else:
                    self.logger.info(f"process proxies got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))

                        site_virtual_sites = r['spec'].get('site_virtual_sites', {})
                        advertise_where = site_virtual_sites.get('advertise_where', [])

                        for site_info in advertise_where:
                            for site_type in site_info.keys():
                                if site_type in c.F5XC_SITE_TYPES:
                                    if site_type == c.F5XC_SITE:
                                        # Referenced site must exist
                                        if site_info[site_type][site_type]['name'] in self.data[c.SITES_KEY]:
                                            site_name = site_info[site_type][site_type]['name']
                                            if self.site:
                                                if self.site == site_name:
                                                    process()
                                            else:
                                                process()
                                    if site_type == c.F5XC_VIRTUAL_SITE:
                                        for s_name, s_values in self.data[c.SITES_KEY].items():
                                            if c.SITE_VIRTUAL_SITES_KEY in s_values:
                                                if len(s_values[c.SITE_VIRTUAL_SITES_KEY]) > 0:
                                                    vsite_name = site_info[site_type][site_type]['name']
                                                    if vsite_name in s_values[c.SITE_VIRTUAL_SITES_KEY]:
                                                        self.logger.debug(f"Virtual site reference detected. virtual_site_name: {vsite_name} site name: {s_name}")
                                                        self.logger.debug(f"swapping site name from VSITE to SITE: {vsite_name} <--> {s_name}")
                                                        site_name = s_name

                                                        if self.site:
                                                            if self.site == site_name:
                                                                process()
                                                        else:
                                                            process()

        return self.data
