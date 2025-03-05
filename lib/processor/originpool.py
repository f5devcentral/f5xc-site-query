import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Originpool(Base):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        """

        :param session:
        :param api_url:
        :param data:
        :param site:
        :param workers:
        :param logger:
        """
        super().__init__(session=session, api_url=api_url, data=data, site=site, workers=workers, logger=logger)

        for namespace in self.data["namespaces"]:
            self.urls.append(self.build_url(c.URI_F5XC_ORIGIN_POOLS.format(namespace=namespace)))

        self.logger.debug("ORIGIN_POOL_URLS: %s", self.urls)

    def run(self) -> dict:
        """
        Add origin pools to site if origin pools refers to a site. Obtains specific origin pool by name.
        :return: structure with origin pool information being added
        """

        _origin_pools = self.execute(name="origin pools", urls=self.urls)

        def process():
            try:
                origin_pool_name = r["metadata"]["name"]
                namespace = r["metadata"]["namespace"]
                if site_name not in self.data[site_type].keys():
                    self.data[site_type][site_name] = dict()
                    self.data[site_type][site_name]['namespaces'] = dict()
                if 'namespaces' not in self.data[site_type][site_name].keys():
                    self.data[site_type][site_name]['namespaces'] = dict()
                if namespace not in self.data[site_type][site_name]['namespaces'].keys():
                    self.data[site_type][site_name]['namespaces'][namespace] = dict()
                if "origin_pools" not in self.data[site_type][site_name]['namespaces'][namespace].keys():
                    self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"] = dict()

                self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"][origin_pool_name] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"][origin_pool_name]['spec'] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"][origin_pool_name]['metadata'] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]["origin_pools"][origin_pool_name]['system_metadata'] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]['origin_pools'][origin_pool_name]['spec'] = r['spec']
                self.data[site_type][site_name]['namespaces'][namespace]['origin_pools'][origin_pool_name]['metadata'] = r['metadata']
                self.data[site_type][site_name]['namespaces'][namespace]['origin_pools'][origin_pool_name]['system_metadata'] = r['system_metadata']

                self.logger.info(f"process origin pools add data: [namespace: {namespace} origin pool: {origin_pool_name} site_type: {site_type} site_name: {site_name}]")
            except Exception as e:
                self.logger.info("site_type:", site_type)
                self.logger.info("site_name:", site_name)
                self.logger.info("namespace:", r["metadata"]["namespace"])
                self.logger.info("system_metadata:", r['system_metadata'])
                self.logger.info("Exception:", e)

        urls = list()

        for item in _origin_pools:
            for url, origin_pools in item.items():
                for origin_pool in origin_pools:
                    _url = "{}/{}".format(url, origin_pool['name'])
                    urls.append(_url)

        self.logger.debug(f"process origin pools url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}
            self.must_break = False

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process origin pools get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process origin pools", _data, exc))
                else:
                    self.logger.info(f"process origin pools got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))
                        origin_servers = r['spec'].get('origin_servers', [])

                        for origin_server in origin_servers:
                            if self.must_break:
                                break
                            else:
                                for key in c.F5XC_ORIGIN_SERVER_TYPES:
                                    if self.must_break:
                                        break
                                    else:
                                        site_locator = origin_server.get(key, {}).get('site_locator', {})

                                        for site_type, site_data in site_locator.items():
                                            site_name = site_data.get('name')

                                            if site_name:
                                                # Referenced site must exist
                                                if site_name in self.data[site_type]:
                                                    # Only processing sites which are not in failed state
                                                    if site_name not in self.data["failed"]:
                                                        if self.site:

                                                            if self.site == site_name:
                                                                self.must_break = True
                                                                process()
                                                                break
                                                        else:
                                                            process()

        return self.data
