import json
from unittest.mock import patch
from prettytable import PrettyTable

import pytest
import logging

from lib.api import Api

API_URL = "https://playground.console.ves.volterra.io/api"
API_TOKEN = "abc123456789"
WORKERS = 10
USER_SPECIFIED_SITE = "site_a"
TEST_DATA_ALL_NS_FILE_NAME = "tests/data/all_ns.json"
TEST_DATA_SITE_OLD_NAME = "f5xc-aws-ce-test-60"
TEST_DATA_SITE_NEW_NAME = "f5xc-aws-ce-test-61"
TEST_DATA_SITE_OLD_FILE_NAME = "tests/data/site_old.json"
TEST_DATA_SITE_NEW_FILE_NAME = "tests/data/site_new.json"


@pytest.fixture
def api():
    with patch.object(Api, "__init__", lambda a, b, c, d, e, f, g: None):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        api = Api(None, None, None, None, None, 10)
        api._api_url = API_URL
        api._api_token = API_TOKEN
        api._workers = WORKERS
        api._logger = logger
        api._site = USER_SPECIFIED_SITE
        with open(TEST_DATA_ALL_NS_FILE_NAME, "r") as fp:
            data = json.load(fp=fp)
        api._data = data
        return api


def test_api_init(api):
    assert api.api_token == API_TOKEN
    assert api.api_url == API_URL
    assert api.workers == WORKERS
    assert api.site == USER_SPECIFIED_SITE


def test_api_compare(api):
    table = api.compare(TEST_DATA_SITE_OLD_NAME, TEST_DATA_SITE_OLD_FILE_NAME, TEST_DATA_SITE_NEW_NAME, TEST_DATA_SITE_NEW_FILE_NAME)
    assert isinstance(table, PrettyTable)
    assert table.field_names == ["path", "values"]
