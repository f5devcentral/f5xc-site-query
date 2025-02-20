import json
import pprint
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base

URL_TYPE = None

class SiteMeshGroup(Base):
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

    def run(self) -> dict | None:
        """
        Add site mesh groups to site if site mesh group refers to a site. Obtains specific site mesh group by name.
        :return: structure with site mesh group information being added
        """

        urls_smg = dict()
        urls_vs = dict()

        _smgs = self.get(self.build_url(c.URI_F5XC_SITE_MESH_GROUPS.format(namespace="system")))

        if _smgs:
            self.logger.debug(json.dumps(_smgs.json(), indent=2))

            for smg in _smgs.json()['items']:
                urls_smg[self.build_url(c.URI_F5XC_SITE_MESH_GROUP.format(namespace="system", name=smg['name']))] = smg['name']

            site_mesh_groups = self.execute(name="site mesh group", urls=urls_smg)
            for smg in site_mesh_groups:
                urls_vs[self.build_url(c.URI_F5XC_VIRTUAL_SITE.format(namespace="shared", name=smg['data']['spec']['virtual_site'][0]['name']))] = smg['data']['metadata']['name']

            # Remove virtual sites without 'site_selector' key
            virtual_sites = [vs for vs in self.execute(name="virtual site", urls=urls_vs) if 'site_selector' in vs['data']['spec']]
            for site in self.data["site"].keys():
                #Store virtual sites current site is a member of
                site_is_member_of_virtual_sites = set()
                # Need to evaluate site_selector expression in virtual site data
                # Split expression into key, operator, value parts. If value is a comma separated list of items split these
                # Compare site label and key with virtual site expression key and value. Supported comparators are "equal" and "in"
                for vs in virtual_sites:
                    _expressions = [exp.split(" ", 2) for exp in vs['data']["spec"]["site_selector"]["expressions"]]
                    expressions = list()

                    for item in _expressions:
                        #If virtual site site_selector expression is a comma separated list of items split these
                        if item[2].startswith("(") and item[2].endswith(")"):
                            val = [a.strip("() ") for a in item[2].split(",")]
                            expressions.append({"key": item[0], "operator": item[1], "value": val})
                        else:
                            expressions.append({"key": item[0], "operator": item[1], "value": item[2]})

                    for label, value in self.data["site"][site]["labels"].items():
                        for expression in expressions:
                            if label == expression["key"] and value == expression["value"]:
                                site_is_member_of_virtual_sites.add(vs["data"]["metadata"]["name"])
                            elif label == expression["key"] and value in expression["value"]:
                                site_is_member_of_virtual_sites.add(vs["data"]["metadata"]["name"])

                # Add virtual sites current site is a member of below new key 'vsites'
                if "vsites" not in self.data["site"][site].keys():
                    self.data["site"][site]["vsites"] = list(site_is_member_of_virtual_sites)

                if "smg" not in self.data["site"][site].keys():
                    self.data["site"][site]["smg"] = dict()
                #Add secure mesh site to site data
                # If secure mesh site virtual site name is in list of virtual sites this site is a member of
                for smg in site_mesh_groups:
                    if smg['data']["spec"]["virtual_site"][0]["name"] in site_is_member_of_virtual_sites:
                        self.data["site"][site]["smg"][smg["data"]["spec"]["virtual_site"][0]["name"]] = dict()
                        self.data["site"][site]["smg"][smg["data"]["spec"]["virtual_site"][0]["name"]]["metadata"] = smg["data"]["metadata"]
                        self.data["site"][site]["smg"][smg["data"]["spec"]["virtual_site"][0]["name"]]["spec"] = smg["data"]["spec"]

        """
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
                        pp.pprint(r)
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
        """

        return self.data
