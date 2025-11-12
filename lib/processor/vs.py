import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Vs(Base):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        """
        A class for processing site related virtual site data.
        :param session: current http session
        :param api_url: api url to connect to
        :param data: data structure to add virtual site data to
        :param site: user injected site name to filter for
        :param workers: amount of concurrent threads
        :param logger: log instance for writing / printing log information
        """
        super().__init__(session=session, api_url=api_url, data=data, site=site, workers=workers, logger=logger)

        # Reset urls
        self.urls = list()

        for namespace in self.data["namespaces"]:
            self.urls.append(self.build_url(c.URI_F5XC_VIRTUAL_SITES.format(namespace=namespace)))

        self.logger.debug("VIRTUAL_SITE_URLS: %s", self.urls)

    def run(self) -> dict | None:
        """
        Get list of virtual sites and process data.
        Add virtual sites to data structure.
        :return: structure with virtual sites information being added
        """

        _virtual_sites = self.execute(name="virtual site details", urls=self.urls)

        def process():
            try:
                vs_name = r["metadata"]["name"]
                self.data[c.VIRTUAL_SITES_KEY][vs_name] = dict()
                self.data[c.VIRTUAL_SITES_KEY][vs_name]['metadata'] = r["metadata"]
                self.data[c.VIRTUAL_SITES_KEY][vs_name]['spec'] = r["spec"]
            except Exception as e:
                self.logger.info("namespace:", r["metadata"]["namespace"])
                self.logger.info("system_metadata:", r['system_metadata'])
                self.logger.info("Exception:", e)

        urls = list()

        for item in _virtual_sites:
            for url, lbs in item.items():
                for lb in lbs:
                    _url = "{}/{}".format(url, lb['name'])
                    urls.append(_url)

        self.logger.debug(f"process virtual site url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]
                self.must_break = False

                try:
                    self.logger.info(f"process virtual site get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process virtual site", _data, exc))
                else:
                    self.logger.info(f"process virtual site got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))
                        process()

        return self.data
