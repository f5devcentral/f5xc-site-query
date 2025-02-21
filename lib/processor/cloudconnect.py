import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Cloudconnect(Base):
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
        Get list of cloud connectors and process data.
        Add cloud connectors to data structure.
        :return: structure with cloud connectors information being added
        """

        def process():
            try:
                cloud_connector_name = cloud_connector["data"]["metadata"]["name"]
                if 'cloud_connector' not in self.data["site"][site].keys():
                    self.data["site"][site]["cloud_connector"] = dict()
                if cloud_connector_name not in self.data["site"][site]["cloud_connector"].keys():
                    self.data["site"][site]["cloud_connector"][cloud_connector_name] = dict()
                self.data["site"][site]['cloud_connector'][cloud_connector_name]['spec'] = dict()
                self.data["site"][site]['cloud_connector'][cloud_connector_name]['metadata'] = dict()
                self.data["site"][site]['cloud_connector'][cloud_connector_name]['system_metadata'] = dict()
                self.data["site"][site]['cloud_connector'][cloud_connector_name]['spec'] = cloud_connector["data"]["spec"]
                self.data["site"][site]['cloud_connector'][cloud_connector_name]['metadata'] = cloud_connector["data"]["metadata"]
                self.data["site"][site]['cloud_connector'][cloud_connector_name]['system_metadata'] = cloud_connector["data"]['system_metadata']

            except Exception as e:
                self.logger.info("connector_type:", connector_type)
                self.logger.info("namespace:", cloud_connector["data"]["metadata"]["namespace"])
                self.logger.info("system_metadata:", cloud_connector["data"]['system_metadata'])
                self.logger.info("Exception:", e)

        self.logger.info(f"process cloud connect objects get all cloud connect objects from {self.build_url(c.URI_F5XC_CLOUD_CONNECTS).format(namespace=c.F5XC_NAMESPACE_SYSTEM)}")
        _ccs = self.get(self.build_url(c.URI_F5XC_CLOUD_CONNECTS).format(namespace=c.F5XC_NAMESPACE_SYSTEM))

        if _ccs:
            self.logger.debug(json.dumps(_ccs.json(), indent=2))
            ccs = [cc for cc in _ccs.json()['items']]
            urls = dict()

            for cc in ccs:
                urls[self.build_url(c.URI_F5XC_CLOUD_CONNECT.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=cc['name']))] = cc['name']

            cloud_connectors = self.execute(name="cloud connector details", urls=urls)
            self.logger.debug(json.dumps(cloud_connectors, indent=2))

            if cloud_connectors:
                for cloud_connector in cloud_connectors:
                    if self.must_break:
                        break
                    else:
                        connector_type = [key for key in c.F5XC_CLOUD_CONNECT_TYPES if key in cloud_connector["data"]["spec"]][0]
                        site = cloud_connector["data"]["spec"][connector_type]["site"]["name"]

                        # Referenced site must exist
                        if site in self.data["site"]:
                            # Only processing sites which are not in failed state
                            if site not in self.data["failed"]:
                                if self.site:
                                    if self.site == site:
                                        self.must_break = True
                                        process()
                                        break

                                else:
                                    process()
        return self.data
