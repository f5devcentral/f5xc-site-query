import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Smg(Base):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        """
        A class for processing site related site mesh group data.
        :param session: current http session
        :param api_url: api url to connect to
        :param data: data structure to add site mesh group data to
        :param site: user injected site name to filter for
        :param workers: amount of concurrent threads
        :param logger: log instance for writing / printing log information
        """
        super().__init__(session=session, api_url=api_url, data=data, site=site, workers=workers, logger=logger)

    def run(self) -> dict | None:
        """
        Add site mesh groups to site if site mesh group refers to a site. Obtains specific site mesh group by name.
        :return: structure with site mesh group information being added
        """

        urls_smg = dict()
        urls_vs = dict()

        _smgs = self.get(self.build_url(c.URI_F5XC_SITE_MESH_GROUPS.format(namespace=c.F5XC_NAMESPACE_SYSTEM)))

        if _smgs:
            self.logger.debug(json.dumps(_smgs.json(), indent=2))

            for smg in _smgs.json()['items']:
                urls_smg[self.build_url(c.URI_F5XC_SITE_MESH_GROUP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=smg['name']))] = smg['name']

            site_mesh_groups = self.execute(name="site mesh group", urls=urls_smg)
            for smg in site_mesh_groups:
                if len(smg['data']['spec']['virtual_site']) > 0:
                    urls_vs[self.build_url(c.URI_F5XC_VIRTUAL_SITE.format(namespace=c.F5XC_NAMESPACE_SHARED, name=smg['data']['spec']['virtual_site'][0]['name']))] = smg['data']['metadata']['name']
                else:
                    self.logger.info(f"failed to add site mesh group info for site: {smg['data']['metadata']['name']}")

            # Remove virtual sites without 'site_selector' key
            virtual_sites = [vs for vs in self.execute(name="virtual site", urls=urls_vs) if 'site_selector' in vs['data']['spec']]
            for site in self.data["site"].keys():
                # Store virtual sites current site is a member of
                site_is_member_of_virtual_sites = set()
                # Need to evaluate site_selector expression in virtual site data
                # Split expression into key, operator, value parts. If value is a comma separated list of items split these
                # Compare site label and key with virtual site expression key and value. Supported comparators are "equal" and "in"
                for vs in virtual_sites:
                    _expressions = list()

                    for exp in vs['data']["spec"]["site_selector"]["expressions"]:
                        if " " in exp:
                            _expressions.append(exp.split(" ", 2))
                        else:
                            _exp = exp.split("=")
                            _exp.insert(1, "=")
                            _expressions.append(_exp)

                    expressions = list()

                    for expression in _expressions:
                        # Check if expression is of from ["key", "operand", "value"]
                        if len(expression) == 3:
                            # If virtual site site_selector expression is a comma separated list of items split these
                            if expression[2].startswith("(") and expression[2].endswith(")"):
                                val = [a.strip("() ") for a in expression[2].split(",")]
                                expressions.append({"key": expression[0], "operator": expression[1], "value": val})
                            else:
                                expressions.append({"key": expression[0], "operator": expression[1], "value": expression[2]})
                        else:
                            self.logger.info(f"Found unsupported selector expression: {expression}")

                    for label, value in self.data["site"][site]["metadata"]["labels"].items():
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
                # Add secure mesh site to site data
                # If secure mesh site virtual site name is in list of virtual sites this site is a member of
                for smg in site_mesh_groups:
                    if len(smg['data']['spec']['virtual_site']) > 0:
                        if smg['data']["spec"]["virtual_site"][0]["name"] in site_is_member_of_virtual_sites:
                            self.data["site"][site]["smg"][smg["data"]["spec"]["virtual_site"][0]["name"]] = dict()
                            self.data["site"][site]["smg"][smg["data"]["spec"]["virtual_site"][0]["name"]]["metadata"] = smg["data"]["metadata"]
                            self.data["site"][site]["smg"][smg["data"]["spec"]["virtual_site"][0]["name"]]["spec"] = smg["data"]["spec"]

        return self.data
