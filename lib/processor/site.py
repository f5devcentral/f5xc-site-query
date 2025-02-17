import concurrent.futures
import json
import pprint
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base

SMS_VERSION = "v1"


class Site(Base):
    def __init__(self, session: Session = None, api_url: str = None, urls: list = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        super().__init__(session=session, api_url=api_url, urls=urls, data=data, site=site, workers=workers, logger=logger)
        self._sites = list()

    @property
    def sites(self):
        return self._sites

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
            self._sites = [site for site in _sites.json()['items'] if self.site == site['name']] if self.site else _sites.json()['items']

            for processor in c.SITE_OBJECT_PROCESSORS:
                getattr(self, f"process_{processor}")()

            sites_with_origin_pools_only = []

            for site_name, site_data in self.data['site'].items():
                if "namespaces" in site_data.keys():
                    for n_name, n_data in site_data['namespaces'].items():
                        # Check if the site has origin pools only
                        if len(n_data.keys()) == 1 and 'origin_pools' in n_data.keys():
                            sites_with_origin_pools_only.append(site_name)

            self.data["sites_with_origin_pools_only"] = sites_with_origin_pools_only
            self.logger.info(f"process sites <{len(sites_with_origin_pools_only)}> sites with origin pools only")

            self.data["orphaned_sites"] = [k for k, v in self.data['site'].items() if 'labels' not in v.keys()]
            self.logger.info(f"process sites <{len(self.data['orphaned_sites'])}> sites without labels (orphaned)")

            return self.data

    def process_site(self):
        """
        Process general site details and add data to specific site.
        Details including for instance enhanced firewall policies, network interfaces, etc.
        :return:
        """

        # Stores site urls build from URI_F5XC_SITE
        urls = dict()

        # Build urls for site
        for site in self.sites:
            urls[self.build_url(c.URI_F5XC_SITE.format(namespace="system", name=site['name']))] = site['name']

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare general site details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process general site details get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process general site details", _data, exc))
                else:
                    self.logger.info(f"process general site details got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))

                        if urls[future_to_ds[future]] in self.data['site']:
                            self.data['site'][urls[future_to_ds[future]]]['metadata'] = r['metadata']
                            self.data['site'][urls[future_to_ds[future]]]['spec'] = r['spec']

                            if r['metadata']['name'] in self.data['site']:
                                self.logger.info(f"process sites add label information to site {r['metadata']['name']}")
                                self.data['site'][urls[future_to_ds[future]]]['labels'] = r['metadata']['labels']

    def process_sms(self):
        """
        Process sms specific site details and add data to specific site.
        Details including for instance enhanced firewall policies, network interfaces, etc.
        :return:
        """

        pp = pprint.PrettyPrinter()
        # Stores site urls build from URI_F5XC_SITE
        urls = dict()

        # Build urls for site
        for site in self.sites:
            if SMS_VERSION == "v1":
                urls[self.build_url(c.URI_F5XC_SMS_V1.format(namespace="system", name=site['name']))] = site['name']
            elif SMS_VERSION == "v2":
                urls[self.build_url(c.URI_F5XC_SMS_V2.format(namespace="system", name=site['name']))] = site['name']

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info(f"Prepare sms {SMS_VERSION} site details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process smv {SMS_VERSION} site details get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process sms site details", _data, exc))
                else:
                    self.logger.info(f"process sms {SMS_VERSION} site details got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))

                        if urls[future_to_ds[future]] in self.data['site']:
                            if "sms" not in self.data['site'][urls[future_to_ds[future]]].keys():
                                self.data['site'][urls[future_to_ds[future]]]['sms'] = dict()

                            self.data['site'][urls[future_to_ds[future]]]['sms']['metadata'] = r['metadata']
                            self.data['site'][urls[future_to_ds[future]]]['sms']['spec'] = r['spec']

    def process_efp(self):
        """
        Process Secure Mesh site enhanced firewall policies details and add data to specific site.
        :return:
        """

        # Build enhanced firewall policy urls for given site
        urls = dict()

        # Get efp name by iterating existing sms data
        for site in self.data['site'].keys():
            if "custom_network_config" in self.data["site"][site]["sms"]["spec"].keys():
                if "active_enhanced_firewall_policies" in self.data["site"][site]["sms"]["spec"]['custom_network_config']:
                    for efp in self.data["site"][site]["sms"]["spec"]['custom_network_config']['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                        urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace="system", name=efp['name']))] = self.data["site"][site]["sms"]['metadata']['name']

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare enhanced firewall policy details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process enhanced firewall policy details get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process site details", _data, exc))
                else:
                    self.logger.info(f"process enhanced firewall policy details got item: {future_to_ds[future]} ...")

                    if result:
                        efp = result.json()
                        self.logger.debug(json.dumps(efp, indent=2))
                        if urls[future_to_ds[future]] in self.data['site']:
                            if "efp" not in self.data['site'][urls[future_to_ds[future]]]:
                                self.data['site'][urls[future_to_ds[future]]]['efp'] = dict()

                            self.data['site'][urls[future_to_ds[future]]]['efp'][efp['metadata']['name']] = dict()
                            self.data['site'][urls[future_to_ds[future]]]['efp'][efp['metadata']['name']]['metadata'] = efp['metadata']
                            self.data['site'][urls[future_to_ds[future]]]['efp'][efp['metadata']['name']]['spec'] = efp['spec']

    def process_fpp(self):
        """
        Process Secure Mesh site forward proxy policy details and add data to specific site.
        :return:
        """

        # Build forward proxy policy urls for given site
        urls = dict()

        # Get efp name by iterating existing sms data
        for site in self.data['site'].keys():
            if "custom_network_config" in self.data["site"][site]["sms"]["spec"].keys():
                if "active_forward_proxy_policies" in self.data["site"][site]["sms"]["spec"]['custom_network_config']:
                    for fpp in self.data["site"][site]["sms"]["spec"]['custom_network_config']['active_forward_proxy_policies']['forward_proxy_policies']:
                        urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace="system", name=fpp['name']))] = self.data["site"][site]["sms"]['metadata']['name']

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare forward proxy policy details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process forward proxy policy details get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process forward proxy policy details", _data, exc))
                else:
                    self.logger.info(f"process forward proxy policy details got item: {future_to_ds[future]} ...")

                    if result:
                        fpp = result.json()
                        self.logger.debug(json.dumps(fpp, indent=2))

                        if urls[future_to_ds[future]] in self.data['site']:
                            if "fpp" not in self.data['site'][urls[future_to_ds[future]]]:
                                self.data['site'][urls[future_to_ds[future]]]['fpp'] = dict()

                            self.data['site'][urls[future_to_ds[future]]]['fpp'][fpp['metadata']['name']] = dict()
                            self.data['site'][urls[future_to_ds[future]]]['fpp'][fpp['metadata']['name']]['metadata'] = fpp['metadata']
                            self.data['site'][urls[future_to_ds[future]]]['fpp'][fpp['metadata']['name']]['spec'] = fpp['spec']

    def process_dc_cluster_group(self):
        """
        Process Secure Mesh site dc cluster group details and add data to specific site.
        :return:
        """
        pp = pprint.PrettyPrinter()
        # Build dc cluster group urls for given site
        urls_slo = dict()
        urls_sli = dict()

        # Get dc cluster group name by iterating existing sms data. Check for SLO and SLI interface if DC cluster group set.
        for site in self.data['site'].keys():
            if "custom_network_config" in self.data["site"][site]["sms"]["spec"].keys():
                if "slo_config" in self.data["site"][site]["sms"]["spec"]['custom_network_config'].keys():
                    if "dc_cluster_group" in self.data["site"][site]["sms"]["spec"]['custom_network_config']["slo_config"].keys():
                        name = self.data["site"][site]["sms"]["spec"]['custom_network_config']['slo_config']['dc_cluster_group']['name']
                        urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data["site"][site]["sms"]['metadata']['name']
                elif "sli_config" in self.data["site"][site]["sms"]["spec"]['custom_network_config']:
                    if "dc_cluster_group" in self.data["site"][site]["sms"]["spec"]['custom_network_config']["sli_config"].keys():
                        name = self.data["site"][site]["sms"]["spec"]['custom_network_config']['slo_config']['dc_cluster_group']['name']
                        urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data["site"][site]["sms"]['metadata']['name']

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare dc cluster group slo details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls_slo.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process dc cluster group slo details get item: {future_to_ds[future]} ...")
                    result = future.result()
                    print(result)
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process dc cluster group details", _data, exc))
                else:
                    self.logger.info(f"process dc cluster group slo details got item: {future_to_ds[future]} ...")

                    if result:
                        dc_cg = result.json()
                        pp.pprint(dc_cg)
                        self.logger.debug(json.dumps(dc_cg, indent=2))

                        if urls_slo[future_to_ds[future]] in self.data['site']:
                            if "dc_cluster_group" not in self.data['site'][urls_slo[future_to_ds[future]]]:
                                self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'] = dict()

                            self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']] = dict()
                            self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['slo'] = dict()
                            self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['slo']['metadata'] = dc_cg['metadata']
                            self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['slo']['spec'] = dc_cg['spec']

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare dc cluster group sli details query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls_sli.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process dc cluster group sli details get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process dc cluster group details", _data, exc))
                else:
                    self.logger.info(f"process dc cluster group sli details got item: {future_to_ds[future]} ...")

                    if result:
                        dc_cg = result.json()
                        self.logger.debug(json.dumps(dc_cg, indent=2))

                        if urls_sli[future_to_ds[future]] in self.data['site']:
                            if "dc_cluster_group" not in self.data['site'][urls_sli[future_to_ds[future]]]:
                                self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'] = dict()

                            self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']] = dict()
                            self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['sli'] = dict()
                            self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['sli']['metadata'] = dc_cg['metadata']
                            self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['sli']['spec'] = dc_cg['spec']



    def process_hw_info(self):
        """
        Process site hardware info and add data to site data.
        :return:
        """

        # Build ce node hardware info urls for given site
        urls = dict()
        for site in self.sites:
            urls[self.build_url(c.URI_F5XC_SITE.format(namespace="system", name=site['name']))] = site['name']

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare site hardware info query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls.keys()}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    self.logger.info(f"process site hardware info get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process site hardware info", _data, exc))
                else:
                    self.logger.info(f"process site hardware info got item: {future_to_ds[future]} ...")

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
