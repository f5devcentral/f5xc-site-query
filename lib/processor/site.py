import concurrent.futures
import json
import pprint
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Site(Base):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        """
        :param session: current http session
        :param api_url: api url to connect to
        :param data: data structure to add site data to
        :param site: user injected site name to filter for
        :param workers: amount of concurrent threads
        :param logger: log instance for writing / printing log information

        A class for processing site related data. A site object directly references certain objects like:
        - efp
        - ffp
        - dc cluster group
        - cloud link
        - spoke
        This referenced objects will be added to site inventory. Additionally, this class provides methods to process site hardware and node interface information

        Methods
        -------
        run()
            start modules to start build site inventory information
        process_site()
            process general site data. Filter sites in available attributes and their status
        process_site_details()
            add site detail information to site inventory. Site details are 'metadata', 'spec', 'main_node_counter', 'worker_node_counter'
        process_efp()
            add referenced enhanced firewall policy information to site inventory
        process_fpp()
            add referenced forward proxy policy information to site inventory
        process_dc_cluster_group()
            add referenced dc cluster group information to site inventory
        process_cloud_link()
            add referenced cloud link information to site inventory
        process_spokes()
            add referenced spokes information to site inventory
        process_node_interfaces()
            add site interface information to site inventory
        process_hw_info()
            add site hardware information to site inventory
        """
        super().__init__(session=session, api_url=api_url, data=data, site=site, workers=workers, logger=logger)

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

            return self.data

        return None

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
            urls[self.build_url(c.URI_F5XC_SITE.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=site['name']))] = site['name']

        _sites = self.execute(name="general site details", urls=urls)
        for site in _sites:
            # Only process sites with a "kind" key set. Sites without "kind" key are malformed
            if site['data']['system_metadata']["owner_view"]:
                if site['data']['system_metadata']["owner_view"]["kind"]:

                    def get_site_status(site_kind: str = None) -> (bool, str):
                        """
                        Get site state according to the site kind. SecureMesh object based sites expose site state in 'site_state' variable below spec key
                        Whereas legacy object based sites expose site state below 'status' key.
                        If site state not "ONLINE" for SecureMesh object based sites and "APPLIED" for legacy object based sites add site to failed site list
                        Error states: APPLY_ERRORED, DESTROY_ERRORED,TIMED_OUT, ...
                        :param site_kind: Site kind is used to determine if SecureMesh object based site or legacy object based site
                        :return: Tuple (if state is APPLIED or ONLINE return True else False, site state string)
                        """

                        if site_kind == c.F5XC_SITE_TYPE_SMS_V1 or site_kind == c.F5XC_SITE_TYPE_SMS_V2:
                            if site["data"]["spec"]["site_state"] == "ONLINE":
                                return True, site["data"]["spec"]["site_state"]
                            else:
                                failed[site['data']['metadata']['name']] = site["data"]["spec"]["site_state"]
                                return False, site["data"]["spec"]["site_state"]
                        else:
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
                                                    return False, _state["deployment"]["apply_status"]["destroy_state"]
                                                else:
                                                    failed[site['data']['metadata']['name']] = _state["deployment"]["apply_status"]["destroy_state"]
                                                    return False, _state["deployment"]["apply_status"]["destroy_state"]

                            failed[site['data']['metadata']['name']] = None
                            return False, None

                    # Process sites which state is True aka "APPLIED"
                    state, msg = get_site_status(site_kind=site['data']['system_metadata']['owner_view']["kind"])

                    if state:
                        self.data['site'][site["object"]] = dict()
                        self.data['site'][site["object"]]['kind'] = site['data']['system_metadata']['owner_view']["kind"]
                        self.data['site'][site["object"]]['main_node_count'] = len(site['data']['spec']['main_nodes'])
                        self.data['site'][site["object"]]['metadata'] = site['data']['metadata']
                        self.data['site'][site["object"]]['spec'] = site['data']['spec']
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
                urls[self.build_url(c.SITE_TYPE_TO_URI_MAP[values['kind']].format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=site))] = site

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

                            # Check if site is voltstack enabled
                            self.data['site'][urls[future_to_ds[future]]]['sub_kind'] = c.F5XC_SITE_VOLT_STACK if "voltstack_cluster" in r["spec"] else None
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
        Processing efp is part of site object since site object provided ref to efp object.
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
                        if self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V2:
                            if "active_enhanced_firewall_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                for efp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                                    urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=efp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                        elif self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V1:
                            if "custom_network_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"].keys():
                                if "active_enhanced_firewall_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']:
                                    for efp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                                        urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=efp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                    elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                        # If AWS TGW does not provide interface mode
                        if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                            if "tgw_security" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                # Check if tgw_security is not None
                                if self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                    if "active_enhanced_firewall_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                        for efp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                                            urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=efp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                        else:
                            # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                            nic_setup = self.get_site_nic_mode(site=site)

                            if nic_setup:
                                if "active_enhanced_firewall_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup].keys():
                                    for efp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['active_enhanced_firewall_policies']['enhanced_firewall_policies']:
                                        urls[self.build_url(c.URI_F5XC_ENHANCED_FW_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=efp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

        if urls:
            efps = self.execute(name="enhanced firewall policy details", urls=urls)

            for efp in efps:
                if efp["object"] in self.data['site']:
                    if "efp" not in self.data['site'][efp["object"]]:
                        self.data['site'][efp["object"]]['efp'] = dict()

                    self.data['site'][efp["object"]]['efp'][efp['data']['metadata']['name']] = dict()
                    self.data['site'][efp["object"]]['efp'][efp['data']['metadata']['name']]['metadata'] = efp['data']['metadata']
                    self.data['site'][efp["object"]]['efp'][efp['data']['metadata']['name']]['spec'] = efp['data']['spec']

        return self.data

    def process_fpp(self) -> dict | None:
        """
        Process Secure Mesh site forward proxy policy details and add data to specific site.
        Processing fpp is part of site object since site object provided ref to fpp object.
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
                        if self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V2:
                            if "active_forward_proxy_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                for fpp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['active_forward_proxy_policies']['forward_proxy_policies']:
                                    urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=fpp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                        elif self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V1:
                            if "custom_network_config" in self.data['site'][site]["sms"]["spec"].keys():
                                if "active_forward_proxy_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']:
                                    for fpp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['active_forward_proxy_policies']['forward_proxy_policies']:
                                        urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=fpp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                    elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                        # If AWS TGW does not provide interface mode
                        if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                            if "tgw_security" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                # Check if tgw_security is not None
                                if self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                    if "active_forward_proxy_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]:
                                        for fpp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["tgw_security"]['active_forward_proxy_policies']['forward_proxy_policies']:
                                            urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=fpp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                        else:
                            # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                            nic_setup = self.get_site_nic_mode(site=site)
                            if nic_setup:
                                if "active_forward_proxy_policies" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]:
                                    for fpp in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['active_forward_proxy_policies']['forward_proxy_policies']:
                                        urls[self.build_url(c.URI_F5XC_FORWARD_PROXY_POLICY.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=fpp['name']))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

        if urls:
            fpps = self.execute(name="forward proxy policy details query", urls=urls)

            for fpp in fpps:
                if fpp["object"] in self.data['site']:
                    if "fpp" not in self.data['site'][fpp["object"]]:
                        self.data['site'][fpp["object"]]['fpp'] = dict()

                    self.data['site'][fpp["object"]]['fpp'][fpp['data']['metadata']['name']] = dict()
                    self.data['site'][fpp["object"]]['fpp'][fpp['data']['metadata']['name']]['metadata'] = fpp['data']['metadata']
                    self.data['site'][fpp["object"]]['fpp'][fpp['data']['metadata']['name']]['spec'] = fpp['data']['spec']

        return self.data

    def process_dc_cluster_group(self) -> dict | None:
        """
        Process dc cluster group details and add data to specific site.
        Processing dc cluster group is part of site object since site object provided ref to dc cluster group object.
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
                        if self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V2:
                            if "dc_cluster_group_slo" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"].keys():
                                name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['dc_cluster_group_slo']['name']
                                urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                            elif "dc_cluster_group_sli" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"].keys():
                                name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['dc_cluster_group_sli']['name']
                                urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                        elif self.data['site'][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V1:
                            if "custom_network_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"].keys():
                                if "slo_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config'].keys():
                                    if "dc_cluster_group" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']["slo_config"].keys():
                                        name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['slo_config']['dc_cluster_group']['name']
                                        urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                                elif "sli_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']:
                                    if "dc_cluster_group" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']["sli_config"].keys():
                                        name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]['custom_network_config']['sli_config']['dc_cluster_group']['name']
                                        urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

                    elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                        # If AWS TGW does not provide interface mode
                        if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                            if "vn_config" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                # Check if vn_config is not None
                                if self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"]:
                                    if "dc_cluster_group_outside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"].keys():
                                        name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"]['dc_cluster_group_outside_vn']['name']
                                        urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                                    elif "dc_cluster_group_inside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"].keys():
                                        name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vn_config"]['dc_cluster_group_inside_vn']['name']
                                        urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                        else:
                            # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                            nic_setup = self.get_site_nic_mode(site=site)
                            if nic_setup:
                                if "dc_cluster_group_outside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup].keys():
                                    name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['dc_cluster_group_outside_vn']['name']
                                    urls_slo[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']
                                elif "dc_cluster_group_inside_vn" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup].keys():
                                    name = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]['dc_cluster_group_inside_vn']['name']
                                    urls_sli[self.build_url(c.URI_F5XC_DC_CLUSTER_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=name))] = self.data['site'][site][self.get_key_from_site_kind(site)]['metadata']['name']

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

    def process_cloudlink(self) -> dict | None:
        """
        Process cloudlink details and add data to specific site.
        Processing cloudlink is part of processing site object since site object provided ref to cloudlink group object.
        :return: structure with cloudlink information being added
        """
        for site, values in self.data['site'].items():
            if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                pass

        return self.data

    def process_spokes(self) -> dict | None:
        for site, values in self.data['site'].items():
            if self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                    if "vpc_attachments" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                        if self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vpc_attachments"]:
                            if "vpc_list" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vpc_attachments"]:
                                if len(self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vpc_attachments"]["vpc_list"]) > 0:
                                    self.data['site'][site]["spoke"] = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["vpc_attachments"]
                elif self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                    nic_setup = self.get_site_nic_mode(site=site)
                    if nic_setup:
                        if "hub" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]:
                            self.data['site'][site]["spoke"] = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["hub"]

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
                        for idx, node in enumerate(values[self.get_key_from_site_kind(site)]['spec']["master_node_configuration"]):
                            if "nodes" not in self.data['site'][site]:
                                self.data['site'][site]['nodes'] = dict()

                            if f"node{idx}" not in self.data['site'][site]['nodes'].keys():
                                self.data['site'][site]['nodes'][f"node{idx}"] = dict()

                            if "interfaces" not in self.data['site'][site]['nodes'][f"node{idx}"].keys():
                                self.data['site'][site]['nodes'][f"node{idx}"]['interfaces'] = dict()

                            self.data['site'][site]['nodes'][f"node{idx}"]['interfaces'] = values[self.get_key_from_site_kind(site)]['spec']['custom_network_config']['interface_list']['interfaces']

            elif self.get_key_from_site_kind(site) == c.SITE_OBJECT_TYPE_LEGACY:
                if self.data['site'][site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                    if "tgw_info" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
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
                                if f"node{idx}" not in self.data['site'][site]['nodes'].keys():
                                    self.data['site'][site]['nodes'][f"node{idx}"] = dict()
                                if "interfaces" not in self.data['site'][site]['nodes'][f"node{idx}"].keys():
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
                    # Check if sub kind exist
                    if self.data['site'][site]["sub_kind"]:
                        # Check if sub kind is voltstack type
                        if self.data['site'][site]["sub_kind"] == c.F5XC_SITE_VOLT_STACK:
                            for idx, node in enumerate(self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["voltstack_cluster"]["az_nodes"]):
                                if "nodes" not in self.data['site'][site]:
                                    self.data['site'][site]['nodes'] = dict()
                                if "node{idx}" not in self.data['site'][site]['nodes']:
                                    self.data['site'][site]['nodes'][f"node{idx}"] = dict()
                                if "interfaces" not in self.data['site'][site]['nodes'][f"node{idx}"]:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces'] = dict()

                                if "local_subnet" in node:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["local"] = node["local_subnet"]
                                # Add cloud site info to every node even it's duplicate data for the sake of iterating through nodes made easier and needs no exception handling
                                if "cloud_site_info" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]:
                                    if "subnet_ids" in self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["cloud_site_info"]:
                                        self.data['site'][site]['nodes'][f"node{idx}"]["cloud_site"] = self.data['site'][site][self.get_key_from_site_kind(site)]["spec"]["cloud_site_info"]["subnet_ids"]
                                    else:
                                        self.logger.info(f"failed to add cloud site info subnet IDs for site: {site}")
                    else:
                        # Evaluate if site object interface configration is ingress or ingress_egress and set dict key accordingly
                        nic_setup = self.get_site_nic_mode(site=site)
                        if nic_setup:
                            for idx, node in enumerate(self.data['site'][site][self.get_key_from_site_kind(site)]["spec"][nic_setup]["az_nodes"]):
                                if "nodes" not in self.data['site'][site]:
                                    self.data['site'][site]['nodes'] = dict()
                                if "node{idx}" not in self.data['site'][site]['nodes']:
                                    self.data['site'][site]['nodes'][f"node{idx}"] = dict()
                                if "interfaces" not in self.data['site'][site]['nodes'][f"node{idx}"]:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces'] = dict()

                                if "local_subnet" in node:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["slo"] = node["local_subnet"]

                                elif "outside_subnet" in node:
                                    self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["slo"] = node["outside_subnet"]

                                elif nic_setup == "ingress_egress_gw":
                                    if "inside_subnet" in node:
                                        self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["sli"] = node["inside_subnet"]
                                    elif "workload_subnet" in node:
                                        self.data['site'][site]['nodes'][f"node{idx}"]['interfaces']["workload"] = node["workload_subnet"]

        return self.data

    def process_hw_info(self) -> dict | None:
        """
        Process site hardware info and add data to site data. process_hw_info only supports sms object based sites.
        Since nodes available below ['status'] key not idempotent nodes are taken from ['spec'] which is.
        :return: structure with label information being added
        """

        # Build ce node hardware info urls for given site
        urls = dict()

        for site in self.data['site'].keys():
            urls[self.build_url(c.URI_F5XC_SITE.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=site))] = site

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
                            # Build nodes structure first if not already created. Since nodes available below ['status'] key not idempotent nodes are taken from ['spec'] which is. :(
                            # Build static mapping between node key and hostname e.g. node0 --> ip-192-168-0-88
                            node_key_to_hostname_map = dict()
                            if "nodes" not in self.data['site'][urls[future_to_ds[future]]].keys():
                                self.data['site'][urls[future_to_ds[future]]]['nodes'] = dict()

                            for idx, node in enumerate(r['spec']['main_nodes']):
                                if f"node{idx}" not in self.data['site'][urls[future_to_ds[future]]]['nodes']:
                                    self.data['site'][urls[future_to_ds[future]]]['nodes'][f"node{idx}"] = dict()

                                # explicitly set hostname since used as filter when adding hw info
                                self.data['site'][urls[future_to_ds[future]]]['nodes'][f"node{idx}"]['hostname'] = node['name']
                                # add node name to hostname mapping
                                node_key_to_hostname_map[node['name']] = f"node{idx}"

                            for node in r['status']:
                                if node['node_info']:
                                    if node['metadata']['creator_class'] == c.F5XC_CREATOR_CLASS_MAURICE and c.F5XC_NODE_PRIMARY in node['node_info']['role']:
                                        # Filter on hostname set in previous step :(.
                                        if node['node_info']['hostname'] in node_key_to_hostname_map:
                                            self.data['site'][urls[future_to_ds[future]]]['nodes'][node_key_to_hostname_map[node['node_info']['hostname']]]['hw_info'] = node['hw_info']
                                        else:
                                            self.logger.info(f"Site {urls[future_to_ds[future]]} node {node['node_info']['hostname']} does not have hardware info available. No node name to hostname mapping found.")

        return self.data
