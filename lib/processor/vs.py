import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Vs(Base):
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
        Get list of virtual sites and process data.
        Add virtual sites to data structure.
        :return: structure with virtual sites information being added
        """

        self.logger.info(f"process virtual sites get all virtual sites from {self.build_url(c.URI_F5XC_VIRTUAL_SITES.format(namespace=c.F5XC_NAMESPACE_SHARED))}")
        _virtual_sites = self.get(self.build_url(c.URI_F5XC_VIRTUAL_SITES.format(namespace=c.F5XC_NAMESPACE_SHARED)))

        if _virtual_sites:
            self.logger.debug(json.dumps(_virtual_sites.json(), indent=2))
            virtual_sites = [vs for vs in _virtual_sites.json()['items'] if self.site == vs['name']] if self.site else _virtual_sites.json()['items']

            if virtual_sites:
                # Stores virtual_site urls build from URI_F5XC_VIRTUAL_SITE
                urls = dict()
                # Build urls for site
                for vs in virtual_sites:
                    urls[self.build_url(c.URI_F5XC_VIRTUAL_SITE.format(namespace=c.F5XC_NAMESPACE_SHARED, name=vs['name']))] = vs['name']

                _virtual_sites = self.execute(name="virtual site details", urls=urls)
                for vs in _virtual_sites:
                    self.data['virtual_site'][vs["site"]] = dict()
                    self.data['virtual_site'][vs["site"]]['metadata'] = vs['data']['metadata']
                    self.data['virtual_site'][vs["site"]]['spec'] = vs['data']['spec']

            return self.data
