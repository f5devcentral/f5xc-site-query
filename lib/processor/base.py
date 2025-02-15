from abc import abstractmethod
from logging import Logger

from requests import Response, Session


class Base(object):
    def __init__(self, session: Session = None, api_url: str = None, urls: list = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        self._session = session
        self.api_url = api_url
        self._site = site
        self.urls = urls
        self._data = data
        self._workers = workers
        self._logger = logger
        self.must_break = False

    @property
    def data(self):
        return self._data

    @property
    def site(self):
        return self._site

    @property
    def session(self):
        return self._session

    @property
    def workers(self):
        return self._workers

    @property
    def logger(self):
        return self._logger

    def get(self, url: str = None) -> Response | bool:
        """
        Run HTTP GET on a given url
        :param url: Actual URL to run GET request on
        :return: requests.Response
        """
        r = self.session.get(url)

        if 200 != r.status_code:
            self.logger.debug("get failed for {} with {}".format(url, r.status_code))
            return False

        return r if r else False

    def build_url(self, uri: str = None) -> str:
        """
        Build url from api url + resource uri
        :param uri: the resource uri
        :return: url string
        """
        return "{}{}".format(self.api_url, uri)

    @abstractmethod
    def run(self) -> dict:
        pass
