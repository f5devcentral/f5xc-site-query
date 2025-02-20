import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Site(Base):
    def __init__(self, session: Session = None, api_url: str = None, urls: list = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        super().__init__(session=session, api_url=api_url, urls=urls, data=data, site=site, workers=workers, logger=logger)

    def run(self) -> dict | None:
        """
        Get list of sites and process labels.
        Store the sites with only origin pools and without origin pools or load balancers.
        Check if the site has origin pools only (and no load balancer).
        Get site details:
            - site mesh group
            - dc cluster group
            - member of virtual sites
            - enhanced firewall policies
            - hardware info
        :return: structure with label information being added
        """

        self.logger.info(f"process sites get all sites from {self.build_url(c.URI_F5XC_SITES)}")
        _sites = self.get(self.build_url(c.URI_F5XC_SITES))

        if _sites:
            self.logger.debug(json.dumps(_sites.json(), indent=2))
            sites = [site for site in _sites.json()['items'] if self.site == site['name']] if self.site else _sites.json()['items']

            if sites:
                self.process_site(sites=sites)

                for processor in c.SITE_OBJECT_PROCESSORS:
                    getattr(self, f"process_{processor}")()

            """
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
            """

            return self.data

    def process_site(self, sites: list = None) -> dict | None:
        """
        Process general site details and add data to specific site.
        Details including for instance enhanced firewall policies, network interfaces, etc.
        :return: structure with label information being added
        """

        # Stores site urls build from URI_F5XC_SITE
        urls = dict()
        # Stores sites with failed state
        failed = dict()
        # Build urls for site
        for site in sites:
            urls[self.build_url(c.URI_F5XC_SITE.format(namespace="system", name=site['name']))] = site['name']

        _sites = self.execute(name="general site details", urls=urls)
        for site in _sites:
            if site['data']['system_metadata']["owner_view"]:
                if site['data']['system_metadata']["owner_view"]["kind"]:

                    def get_site_status() -> (bool, str):
                        """
                        Get site state. If site state not "APPLIED" add site to failed site list
                        APPLY_ERRORED, DESTROY_ERRORED,TIMED_OUT, ...
                        :return: Tuple (if state is APPLIED return True else False, site state string)
                        """
                        for _state in site["data"]["status"]:
                            if "deployment" in _state:
                                if _state["deployment"]:
                                    if _state["deployment"]["apply_status"]:
                                        if "apply_state" in _state["deployment"]["apply_status"]:
                                            if _state["deployment"]["apply_status"]["apply_state"] == "APPLIED":
                                                return True, _state["deployment"]["apply_status"]["apply_state"]
                                            else:
                                                failed[site['data']['metadata']['name']] = _state["deployment"]["apply_status"]["apply_state"]
                                                return False, _state["deployment"]["apply_status"]["apply_state"]

                                        elif "infra_state" in _state["deployment"]["apply_status"]:
                                            if _state["deployment"]["apply_status"]["infra_state"] == "APPLIED":
                                                return True, _state["deployment"]["apply_status"]["infra_state"]
                                            else:
                                                failed[site['data']['metadata']['name']] = _state["deployment"]["apply_status"]["infra_state"]
                                                return False, _state["deployment"]["apply_status"]["infra_state"]

                                        elif "destroy_state" in _state["deployment"]["apply_status"]:
                                            if _state["deployment"]["apply_status"]["destroy_state"] == "DESTROYED":
                                                return True, _state["deployment"]["apply_status"]["destroy_state"]
                                            else:
                                                failed[site['data']['metadata']['name']] = _state["deployment"]["apply_status"]["destroy_state"]
                                                return False, _state["deployment"]["apply_status"]["destroy_state"]

                        return False, None

                    # Process sites which state is True aka "APPLIED"
                    state, msg = get_site_status()
                    if state:
                        self.data['site'][site["site"]] = dict()
                        self.data['site'][site["site"]]['kind'] = site['data']['system_metadata']['owner_view']["kind"]
                        self.data['site'][site["site"]]['main_node_count'] = len(site['data']['spec']['main_nodes'])
                        self.data['site'][site["site"]]['metadata'] = site['data']['metadata']
                        self.data['site'][site["site"]]['spec'] = site['data']['spec']

                        if site['site'] in self.data['site']:
                            self.logger.info(f"process sites add label information to site {site['site']}")
                            self.data['site'][site["site"]]['labels'] = site['data']['metadata']['labels']
            else:
                if "untyped" not in self.data:
                    self.data['untyped'] = list()

                self.data["untyped"].append(site['data']["metadata"]["name"])

        # Add failed site dict to data
        if "failed" not in self.data:
            self.data['failed'] = failed

        return self.data

    def process_site_details(self) -> dict | None:
        """
        Get site type specific details and add data to site data.
        Details including for instance enhanced firewall policies, network interfaces, etc.
        :return: structure with label information being added
        """

        # Stores site urls build from URI_F5XC_SITE
        urls = dict()

        # Build urls for site
        for site, values in self.data['site'].items():
            if 'kind' in values.keys():
                urls[self.build_url(c.SITE_TYPE_TO_URI_MAP[values['kind']].format(namespace="system", name=site))] = site

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info(f"Prepare site details query...")
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
                            if self.get_key_from_site_kind(urls[future_to_ds[future]]) not in self.data['site'][urls[future_to_ds[future]]].keys():
                                self.data['site'][urls[future_to_ds[future]]][self.get_key_from_site_kind(urls[future_to_ds[future]])] = dict()

                            self.data['site'][urls[future_to_ds[future]]][self.get_key_from_site_kind(urls[future_to_ds[future]])]['metadata'] = r['metadata']
                            self.data['site'][urls[future_to_ds[future]]][self.get_key_from_site_kind(urls[future_to_ds[future]])]['spec'] = r['spec']

                            if "worker_nodes" in r['spec'].keys():
                                self.data['site'][urls[future_to_ds[future]]]['worker_node_count'] = len(r['spec']['worker_nodes'])

                            # check if sms or legacy object type
                            if self.get_key_from_site_kind(urls[future_to_ds[future]]) == c.SITE_OBJECT_TYPE_LEGACY:
                                # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                                nic_setup = self.get_site_nic_mode(site=urls[future_to_ds[future]])

                                if nic_setup:
                                    # Set main node counter
                                    if "az_nodes" in self.data['site'][urls[future_to_ds[future]]][self.get_key_from_site_kind(urls[future_to_ds[future]])]["spec"][nic_setup]:
                                        self.data['site'][urls[future_to_ds[future]]]['main_node_count'] = len(self.data['site'][urls[future_to_ds[future]]][self.get_key_from_site_kind(urls[future_to_ds[future]])]["spec"][nic_setup]['az_nodes'])

        return self.data

    def process_efp(self) -> dict | None:
        """
        Process enhanced firewall policies details and add data to specific site.
        :return: structure with label information being added
        """

        # Build enhanced firewall policy urls for given site
        urls = dict()

        # Get efp name by iterating existing sms data
        for site in self.data['site'].keys():
            if "kind" in self.data['site'][site].keys():
                if self.data['site'][site]['kind'] != "":
                    # check if sms or legacy object type
                    if self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_SMS:
                        if "custom_network_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"].keys():
                            if "active_enhanced_firewall_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']:
                                for efp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                                    urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace="system", name=efp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                    elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                        # If AWS TGW does not provide interface mode
                        if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                            if "tgw_security" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                # Check if tgw_security is not None
                                if self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                    if "active_enhanced_firewall_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                        for efp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                                            urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace="system", name=efp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                        else:
                            # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                            nic_setup = self.get_site_nic_mode(site=site)

                            if nic_setup:
                                if "active_enhanced_firewall_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup].keys():
                                    for efp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                                        urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace="system", name=efp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

        if urls:
            efps = self.execute(name="enhanced firewall policy details", urls=urls)

            for efp in efps:
                if efp["site"] in self.data['site']:
                    if "efp" not in self.data['site'][efp["site"]]:
                        self.data['site'][efp["site"]]['efp'] = dict()

                    self.data['site'][efp["site"]]['efp'][efp['data']['metadata']['name']] = dict()
                    self.data['site'][efp["site"]]['efp'][efp['data']['metadata']['name']]['metadata'] = efp['data']['metadata']
                    self.data['site'][efp["site"]]['efp'][efp['data']['metadata']['name']]['spec'] = efp['data']['spec']

        return self.data

    def process_fpp(self) -> dict | None:
        """
        Process Secure Mesh site forward proxy policy details and add data to specific site.
        :return: structure with label information being added
        """

        # Build forward proxy policy urls for given site
        urls = dict()

        # Get fpp name by iterating existing sms data
        for site in self.data['site'].keys():
            if "kind" in self.data['site'][site].keys():
                if self.data['site'][site]['kind'] != "":
                    # check if sms or legacy object type
                    if self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_SMS:
                        if "custom_network_config" in self.data['site'][site]["sms"]["spec"].keys():
                            if "active_forward_proxy_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']:
                                for fpp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['active_forward_proxy_policies']['forward_proxy_policies']:
                                    urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace="system", name=fpp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                    elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                        # If AWS TGW does not provide interface mode
                        if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                            if "tgw_security" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                # Check if tgw_security is not None
                                if self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                    if "active_forward_proxy_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                        for fpp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]['active_forward_proxy_policies']['forward_proxy_policies']:
                                            urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace="system", name=fpp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                        else:
                            # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                            nic_setup = self.get_site_nic_mode(site=site)
                            if nic_setup:
                                if "active_forward_proxy_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]:
                                    for fpp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['active_forward_proxy_policies']['forward_proxy_policies']:
                                        urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace="system", name=fpp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

        if urls:
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

        return self.data

    def process_dc_cluster_group(self) -> dict | None:
        """
        Process dc cluster group details and add data to specific site.
        :return: structure with dc cluster group information being added
        """

        # Build dc cluster group urls for given site
        urls_slo = dict()
        urls_sli = dict()

        # Get dc cluster group name by iterating existing sms data. Check for SLO and SLI interface if DC cluster group set.
        for site in self.data['site'].keys():
            if "kind" in self.data['site'][site].keys():
                if self.data['site'][site]['kind'] != "":
                    # check if sms or legacy object type
                    if self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_SMS:
                        if "custom_network_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"].keys():
                            if "slo_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config'].keys():
                                if "dc_cluster_group" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']["slo_config"].keys():
                                    name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['slo_config']['dc_cluster_group']['name']
                                    urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                            elif "sli_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']:
                                if "dc_cluster_group" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']["sli_config"].keys():
                                    name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['sli_config']['dc_cluster_group']['name']
                                    urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                    elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                        # If AWS TGW does not provide interface mode
                        if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                            if "vn_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                # Check if vn_config is not None
                                if self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"]:
                                    if "dc_cluster_group_outside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"].keys():
                                        name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"]['dc_cluster_group_outside_vn']['name']
                                        urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                                    elif "dc_cluster_group_inside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"].keys():
                                        name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"]['dc_cluster_group_inside_vn']['name']
                                        urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                        else:
                            # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                            nic_setup = self.get_site_nic_mode(site=site)
                            if nic_setup:
                                if "dc_cluster_group_outside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup].keys():
                                    name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['dc_cluster_group_outside_vn']['name']
                                    urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                                elif "dc_cluster_group_inside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup].keys():
                                    name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['dc_cluster_group_inside_vn']['name']
                                    urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace="system", name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

        if urls_slo:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
                self.logger.info("Prepare dc cluster group slo details query...")
                future_to_ds = {executor.submit(self.get, url=url): url for url in urls_slo.keys()}

                for future in concurrent.futures.as_completed(future_to_ds):
                    _data = future_to_ds[future]

                    try:
                        self.logger.info(f"process dc cluster group slo details get item: {future_to_ds[future]} ...")
                        result = future.result()
                    except Exception as exc:
                        self.logger.info('%s: %r generated an exception: %s' % ("process dc cluster group details", _data, exc))
                    else:
                        self.logger.info(f"process dc cluster group slo details got item: {future_to_ds[future]} ...")

                        if result:
                            dc_cg = result.json()
                            self.logger.debug(json.dumps(dc_cg, indent=2))

                            if urls_slo[future_to_ds[future]] in self.data['site']:
                                if "dc_cluster_group" not in self.data['site'][urls_slo[future_to_ds[future]]]:
                                    self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'] = dict()

                                self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']] = dict()
                                self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['slo'] = dict()
                                self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['slo']['metadata'] = dc_cg['metadata']
                                self.data['site'][urls_slo[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['slo']['spec'] = dc_cg['spec']
        if urls_sli:
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

                                self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']] = dict()
                                self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['sli'] = dict()
                                self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['sli']['metadata'] = dc_cg['metadata']
                                self.data['site'][urls_sli[future_to_ds[future]]]['dc_cluster_group'][dc_cg['metadata']['name']]['sli']['spec'] = dc_cg['spec']

        return self.data

    def process_node_interfaces(self) -> dict | None:
        """
        Process node interface information according to site kind and add data to site data.
        :return: structure with interface information being added
        """

        self.logger.info("Process node interfaces...")

        for site, values in self.data['site'].items():
            # check if sms or legacy object type
            if self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_SMS:
                if "custom_network_config" in values[self.get_key_from_site_kind(site)]['spec'].keys():
                    if "interface_list" in values[self.get_key_from_site_kind(site)]['spec']['custom_network_config'].keys():
                        for node in values[self.get_key_from_site_kind(site)]['spec']["master_node_configuration"]:
                            if "nodes" not in self.data['site'][site]:
                                self.data['site'][site]['nodes'] = dict()

                            if node['name'] not in self.data['site'][site]['nodes'].keys():
                                self.data['site'][site]['nodes'][node['name']] = dict()

                            if "interfaces" not in self.data['site'][site]['nodes'][node['name']].keys():
                                self.data['site'][site]['nodes'][node['name']]['interfaces'] = dict()

                            self.data['site'][site]['nodes'][node['name']]['interfaces'] = values[self.get_key_from_site_kind(site)]['spec']['custom_network_config']['interface_list']['interfaces']

            elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                    if "tgw_info" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                        print("we should add interface info for tgw")
                        print(site)
                        # TGW is always multi NIC hence no nic_setup check
                        for idx, node in enumerate(self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["aws_parameters"]["az_nodes"]):
                            if "nodes" not in self.data['site'][site]:
                                self.data['site'][site]['nodes'] = dict()
                                self.data['site'][site]['nodes'][f"node{idx}"] = dict()
                                self.data['site'][site]['nodes'][f"node{idx}"]['interfaces'] = dict()

                                if "outside_subnet" in node:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["slo"] = node["outside_subnet"]

                                if "workload_subnet" in node:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["workload"] = node["workload_subnet"]

                elif self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_GCP_VPC:
                    nic_setup = self.get_site_nic_mode(site=site)
                    if nic_setup:
                        for idx in range(self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["node_number"]):
                            if "nodes" not in self.data['site'][site]:
                                self.data['site'][site]['nodes'] = dict()
                                self.data['site'][site]['nodes'][f"node{idx}"] = dict()
                                self.data['site'][site]['nodes'][f"node{idx}"]['interfaces'] = dict()

                            if "inside_network" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]:
                                self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["sli"] = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["inside_network"]
                                if "inside_subnet" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["sli"]["subnet"] = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["inside_subnet"]

                            if "outside_network" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]:
                                self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["slo"] = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["outside_network"]
                                if "outside_subnet" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["slo"]["subnet"] = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["outside_subnet"]
                else:
                    # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                    nic_setup = self.get_site_nic_mode(site=site)
                    if nic_setup:
                        for idx, node in enumerate(self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["az_nodes"]):
                            if "nodes" not in self.data['site'][site]:
                                self.data['site'][site]['nodes'] = dict()
                                self.data['site'][site]['nodes'][f"node{idx}"] = dict()
                                self.data['site'][site]['nodes'][f"node{idx}"]['interfaces'] = dict()

                                if "local_subnet" in node:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["slo"] = node["local_subnet"]

                                if "outside_subnet" in node:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["slo"] = node["outside_subnet"]

                                if nic_setup == "ingress_egress_gw":
                                    if "inside_subnet" in node:
                                        self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["sli"] = node["inside_subnet"]
                                    elif "workload_subnet" in node:
                                        self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["workload"] = node["workload_subnet"]

        return self.data

    def process_hw_info(self) -> dict | None:
        """
        Process site hardware info and add data to site data.
        process_hw_info only supports sms object based sites
        :return: structure with label information being added
        """

        # Build ce node hardware info urls for given site
        urls = dict()

        for site in self.data['site'].keys():
            urls[self.build_url(c.URI_F5XC_SITE.format(namespace="system", name=site))] = site

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

                                        if node['node_info']['hostname'] not in self.data['site'][urls[future_to_ds[future]]]['nodes']:
                                            self.data['site'][urls[future_to_ds[future]]]['nodes'][node['node_info']['hostname']] = dict()

                                        self.data['site'][urls[future_to_ds[future]]]['nodes'][node['node_info']['hostname']]['hw_info'] = node['hw_info']

        return self.data
