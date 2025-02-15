import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c

from lib.processor.base import Base


class SiteMeshGroup(Base):
    def __init__(self, session: Session = None, api_url: str = None, urls: list = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        super().__init__(session=session, api_url=api_url, urls=urls, data=data, site=site, workers=workers, logger=logger)
        self.lbs = list()
        self._site_mesh_groups = list()

    @property
    def site_mesh_groups(self):
        return self._site_mesh_groups

    def run(self) -> dict:
        """
        Add site mesh groups to site if site mesh group refers to a site. Obtains specific site mesh group by name.
        :return: structure with site mesh group information being added
        """

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare site mesh groups query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in self.urls}
            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    data = future.result()
                except Exception as exc:
                    self.logger.info('%r generated an exception: %s' % (_data, exc))
                else:
                    self.site_mesh_groups.append({future_to_ds[future]: data.json()["items"]}) if data and data.json()["items"] else None

        def process():
            try:
                site_mesh_group_name = r["metadata"]["name"]
                namespace = r["metadata"]["namespace"]
                if site_name not in self.data[site_type].keys():
                    self.data[site_type][site_name] = dict()
                    self.data[site_type][site_name]['namespaces'] = dict()
                if namespace not in self.data[site_type][site_name]['namespaces'].keys():
                    self.data[site_type][site_name]['namespaces'][namespace] = dict()
                if "site_mesh_groups" not in self.data[site_type][site_name]['namespaces'][namespace].keys():
                    self.data[site_type][site_name]['namespaces'][namespace]["site_mesh_groups"] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]["site_mesh_groups"][site_mesh_group_name] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]["site_mesh_groups"][site_mesh_group_name]['spec'] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]["site_mesh_groups"][site_mesh_group_name]['metadata'] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]["site_mesh_groups"][site_mesh_group_name]['system_metadata'] = dict()
                self.data[site_type][site_name]['namespaces'][namespace]['site_mesh_groups'][site_mesh_group_name]['spec'] = r['spec']
                self.data[site_type][site_name]['namespaces'][namespace]['site_mesh_groups'][site_mesh_group_name]['metadata'] = r['metadata']
                self.data[site_type][site_name]['namespaces'][namespace]['site_mesh_groups'][site_mesh_group_name]['system_metadata'] = r['system_metadata']
                self.logger.info(f"process site mesh group add data: [namespace: {namespace} site mesh group: {site_mesh_group_name} site_type: {site_type} site_name: {site_name}]")
            except Exception as e:
                self.logger.info("site_type:", site_type)
                self.logger.info("site_name:", site_name)
                self.logger.info("namespace:", r["metadata"]["namespace"])
                self.logger.info("system_metadata:", r['system_metadata'])
                self.logger.info("Exception:", e)

        urls = list()

        for item in self.site_mesh_groups:
            for url, site_mesh_groups in item.items():
                for site_mesh_group in site_mesh_groups:
                    _url = "{}/{}".format(url, site_mesh_group['name'])
                    urls.append(_url)

        self.logger.debug(f"process site mesh groups url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}
            self.must_break = False

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process site mesh group get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process site mesh groups", _data, exc))
                else:
                    self.logger.info(f"process site mesh groups got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))
                        site_mesh_groups = r['spec'].get('site_mesh_group', [])

                        for site_mesh_group in site_mesh_groups:
                            print("SMG:", site_mesh_group)
                            if self.must_break:
                                break
                            else:
                                for key in c.F5XC_ORIGIN_SERVER_TYPES:
                                    if self.must_break:
                                        break
                                    else:
                                        site_locator = site_mesh_group.get(key, {}).get('site_locator', {})

                                        for site_type, site_data in site_locator.items():
                                            site_name = site_data.get('name')

                                            if site_name:
                                                if self.site:
                                                    if self.site == site_name:
                                                        self.must_break = True
                                                        process()
                                                        break
                                                else:
                                                    process()

        return self.data
