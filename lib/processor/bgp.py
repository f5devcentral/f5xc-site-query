import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Bgp(Base):
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
        Get list of bgp objects. Add bgp object data to site. If site does not exist add site.
        :return: structure with bgp information being added
        """

        def process():
            try:
                bgp_name = r["metadata"]["name"]
                site_name = r['spec']['where'][site_type]["ref"][0]['name']
                if site_name not in self.data[site_type].keys():
                    self.data[site_type][site_name] = dict()
                if 'bgp' not in self.data[site_type][site_name].keys():
                    self.data[site_type][site_name]['bgp'] = dict()
                self.data[site_type][site_name]['bgp'][bgp_name] = dict()
                self.data[site_type][site_name]['bgp'][bgp_name]['spec'] = dict()
                self.data[site_type][site_name]['bgp'][bgp_name]['metadata'] = dict()
                self.data[site_type][site_name]['bgp'][bgp_name]['system_metadata'] = dict()
                self.data[site_type][site_name]['bgp'][bgp_name]['spec'] = r['spec']
                self.data[site_type][site_name]['bgp'][bgp_name]['metadata'] = r['metadata']
                self.data[site_type][site_name]['bgp'][bgp_name]['system_metadata'] = r['system_metadata']

            except Exception as e:
                self.logger.info("site_type:", site_type)
                self.logger.info("namespace:", r["metadata"]["namespace"])
                self.logger.info("system_metadata:", r['system_metadata'])
                self.logger.info("Exception:", e)

        self.logger.info(f"process bpg get all bgp objects from {self.build_url(c.URI_F5XC_BGPS).format(namespace=c.F5XC_NAMESPACE_SYSTEM)}")
        _bgps = self.get(self.build_url(c.URI_F5XC_BGPS).format(namespace=c.F5XC_NAMESPACE_SYSTEM))

        if _bgps:
            self.logger.debug(json.dumps(_bgps.json(), indent=2))
            bgps = [bgp for bgp in _bgps.json()['items']]
            urls = dict()

            for bgp in bgps:
                urls[self.build_url(c.URI_F5XC_BGP.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=bgp['name']))] = bgp['name']

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
                self.logger.info("Prepare bgp query...")
                future_to_ds = {executor.submit(self.get, url=url): url for url in urls}

                for future in concurrent.futures.as_completed(future_to_ds):
                    _data = future_to_ds[future]

                    try:
                        result = future.result()
                    except Exception as exc:
                        self.logger.info('%r generated an exception: %s' % (_data, exc))
                    else:
                        self.logger.info(f"process bgp got item: {future_to_ds[future]} ...")

                        if result:
                            r = result.json()
                            self.logger.debug(json.dumps(r, indent=2))

                            if 'where' in r['spec']:
                                for site_type in r['spec']['where'].keys():
                                    if self.must_break:
                                        break
                                    else:
                                        if site_type in c.F5XC_SITE_TYPES:
                                            # Referenced site must exist
                                            if r['spec']['where'][site_type]["ref"][0]['name'] in self.data[site_type]:
                                                # Only processing sites which are not in failed state
                                                if r['spec']['where'][site_type]["ref"][0]['name'] not in self.data["failed"]:
                                                    if self.site:
                                                        if self.site == r['spec']['where'][site_type]["ref"][0]['name']:
                                                            self.must_break = True
                                                            process()
                                                            break
                                                    else:
                                                        process()

        return self.data
