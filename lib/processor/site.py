import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c

from lib.processor.base import Base


class Site(Base):
    def __init__(self, session: Session = None, api_url: str = None, urls: list = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        super().__init__(session=session, api_url=api_url, urls=urls, data=data, site=site, workers=workers, logger=logger)
        self.lbs = list()

    def run(self) -> dict | None:
        """
        Get list of sites and process labels. Only add labels to sites that are referenced by a LB/origin_pool/proxys object.
        Store the sites with only origin pools and without origin pools or load balancers.
        Check if the site has origin pools only (and no load balancer). Get site details hw info.
        :return: structure with label information being added
        """

        self.logger.info(f"process sites get all sites from {self.build_url(c.URI_F5XC_SITES)}")
        _sites = self.get(self.build_url(c.URI_F5XC_SITES))

        if _sites:
            self.logger.debug(json.dumps(_sites.json(), indent=2))
            sites = [site for site in _sites.json()['items'] if self.site == site['name']] if self.site else _sites.json()['items']
            # Stores site urls build from URI_F5XC_SITE
            urls_site = dict()
            # Stores site urls build from URI_F5XC_SMS_V1
            urls_sms_v1 = dict()

            for site in sites:
                urls_site[self.build_url(c.URI_F5XC_SITE.format(name=site['name']))] = site['name']
                urls_sms_v1[self.build_url(c.URI_F5XC_SMS_V1.format(namespace="system", name=site['name']))] = site['name']

                if site['name'] in self.data['site']:
                    self.logger.info(f"process sites add label information to site {site['name']}")
                    self.data['site'][site['name']]['labels'] = site['labels']

            sites_with_origin_pools_only = []

            for site_name, site_data in self.data['site'].items():
                for n_name, n_data in site_data['namespaces'].items():
                    # Check if the site has origin pools only
                    if len(n_data.keys()) == 1 and 'origin_pools' in n_data.keys():
                        sites_with_origin_pools_only.append(site_name)

            self.data["sites_with_origin_pools_only"] = sites_with_origin_pools_only
            self.logger.info(f"process sites <{len(sites_with_origin_pools_only)}> sites with origin pools only")

            self.data["orphaned_sites"] = [k for k, v in self.data['site'].items() if 'labels' not in v.keys()]
            self.logger.info(f"process sites <{len(self.data['orphaned_sites'])}> sites without labels (orphaned)")

            self.process_smv1_site_details(urls=urls_sms_v1)
            self.process_site_details(urls=urls_site)

            return self.data

    def process_smv1_site_details(self, urls: dict = None):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare sms v1 site details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process smv v1 site details get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process site details", _data, exc))
                else:
                    self.logger.info(f"process sms v1 site details got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))
                        if urls[future_to_ds[future]] in self.data['site']:
                            if "sms_v1" not in self.data['site'][urls[future_to_ds[future]]].keys():
                                self.data['site'][urls[future_to_ds[future]]]['sms_v1'] = dict()

                            self.data['site'][urls[future_to_ds[future]]]['sms_v1']['metadata'] = r['metadata']
                            self.data['site'][urls[future_to_ds[future]]]['sms_v1']['spec'] = r['spec']

    def process_site_details(self, urls: dict = None):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare site details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process site details get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process site details", _data, exc))
                else:
                    self.logger.info(f"process site details got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))
                        if urls[future_to_ds[future]] in self.data['site']:
                            for node in r['status']:
                                if node['node_info']:
                                    if c.F5XC_NODE_PRIMARY in node['node_info']['role']:
                                        if "nodes" not in self.data['site'][urls[future_to_ds[future]]].keys():
                                            self.data['site'][urls[future_to_ds[future]]]['nodes'] = dict()

                                        self.data['site'][urls[future_to_ds[future]]]['nodes'][node['node_info']['hostname']] = dict()
                                        self.data['site'][urls[future_to_ds[future]]]['nodes'][node['node_info']['hostname']]['hw_info'] = node['hw_info']
