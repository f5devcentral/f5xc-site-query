import json
from logging import Logger
from os import sched_getparam

from requests import Session

import lib.const as c
from lib.processor.base import Base


class Segment(Base):
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
        Get list of segments and process data.
        Add segments to data structure.
        :return: structure with segments information being added
        """

        def process():
            try:
                for site in self.data["site"]:
                    if site == site_name:
                        segment_name = segment["data"]["metadata"]["name"]
                        if 'segment' not in self.data["site"][site].keys():
                            self.data["site"][site]["segments"] = dict()
                        if segment_name not in self.data["site"][site]["segments"].keys():
                            self.data["site"][site]["segments"][segment_name] = dict()
                        self.data["site"][site]['segments'][segment_name]['spec'] = dict()
                        self.data["site"][site]['segments'][segment_name]['metadata'] = dict()
                        self.data["site"][site]['segments'][segment_name]['system_metadata'] = dict()
                        self.data["site"][site]['segments'][segment_name]['spec'] = segment["data"]["spec"]
                        self.data["site"][site]['segments'][segment_name]['metadata'] = segment["data"]["metadata"]
                        self.data["site"][site]['segments'][segment_name]['system_metadata'] = segment["data"]['system_metadata']

            except Exception as e:
                self.logger.info("segment_name:", segment["data"]["metadata"]["name"])
                self.logger.info("namespace:", segment["data"]["metadata"]["namespace"])
                self.logger.info("system_metadata:", segment["data"]['system_metadata'])
                self.logger.info("Exception:", e)

        self.logger.info(f"process segments get all cloud connect objects from {self.build_url(c.URI_F5XC_SEGMENTS).format(namespace=c.F5XC_NAMESPACE_SYSTEM)}")
        _segments = self.get(self.build_url(c.URI_F5XC_SEGMENTS).format(namespace=c.F5XC_NAMESPACE_SYSTEM))

        if _segments:
            self.logger.debug(json.dumps(_segments.json(), indent=2))
            tmp_segments = [segment for segment in _segments.json()['items']]
            urls = dict()

            for segment in tmp_segments:
                urls[self.build_url(c.URI_F5XC_SEGMENT.format(namespace=c.F5XC_NAMESPACE_SYSTEM, name=segment['name']))] = segment['name']

            segments = self.execute(name="segment details", urls=urls)
            self.logger.debug(json.dumps(segments, indent=2))

            if segments:
                for segment in segments:
                    if self.must_break:
                        break
                    else:
                        for attachment in segment["data"]["spec"]["attachments"]:
                            site_name = attachment["site"]

                            # Referenced site must exist
                            if site_name in self.data["site"]:
                                # Only processing sites which are not in failed state
                                if site_name not in self.data["failed"]:
                                    if self.site:
                                        if self.site == site_name:
                                            self.must_break = True
                                            process()
                                            break
                                    else:
                                        process()
        return self.data
