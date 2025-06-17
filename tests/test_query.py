import json
import logging
import os
import time

import pytest
from jsondiff import diff
from prettytable import PrettyTable

from lib.api import Api

API_URL = os.environ.get("API_URL")
API_TOKEN = os.environ.get("API_TOKEN")
WORKERS = 10
USER_SPECIFIED_SITE = "smeshsiteongoing-singlenode"
TEST_DATA_SITE_FILE_NAME = "../json/smeshsiteongoing-singlenode-2.json"

TEST_DATA_SITE_OLD_NAME = "smeshsiteongoing-singlenode"
TEST_DATA_SITE_NEW_NAME = "ongoing-aws-crt-multi-sm2"

# The below 2 vars are used in case of compare functionality tc.
# Run the query manually and store json inside the file_names as below. They are manually created by user at the time of verification of the tc
TEST_DATA_SITE_OLD_FILE_NAME_2 = "../json/smeshsiteongoing-singlenode.json"  # read file
TEST_DATA_SITE_NEW_FILE_NAME_2 = "../json/ongoing-aws-crt-multi-sm2.json"  # read file

GET_NAMESPACE = "ongoing-tests"
GET_NAMESPACE_FILE = "../json/all_ns-2.json"

# The below 2 vars are used inside the inventory tc.
INVENTORY_FILE_CSV = "../csv/site-inventory-2.csv"
TEST_DATA_SITE_OLD_FILE_NAME_REPLICA = "../json/smeshsiteongoing-singlenode.json"  # read file

DIFF_FILE_CSV = "../csv/diff-file-2.csv"

# Configure the logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# This is a test to verify the query functionality using the given site name.
# It is validates the functionality of cmd: ./get-sites.py -a <api> -t <token> -f <file_pathname_where_json_is_stored> -s <site_name> -q --log-stdout
def test_api_site_query():
    start_time = time.perf_counter()
    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=None, site=USER_SPECIFIED_SITE,
            workers=WORKERS)
    q.run()
    q.write_json_file(TEST_DATA_SITE_FILE_NAME)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f'Query time: {int(elapsed_time)} seconds with {WORKERS} workers')

    # Ensure file was created
    assert os.path.exists(TEST_DATA_SITE_FILE_NAME), f"{TEST_DATA_SITE_FILE_NAME} was not created."

    # Validate file contents
    with open(TEST_DATA_SITE_FILE_NAME, "r") as f:
        data = json.load(f)

    # Check on structure (fit actual expected structure) as well as to check if the data is not empty
    assert isinstance(data, dict) or isinstance(data, list), "Output JSON is not a dict or list."
    assert len(data) > 0, "Output file is empty."

    # Clean up file where retrieved json is stored
    os.remove(TEST_DATA_SITE_FILE_NAME)


# This test verifies query functionality using the given namespace name.
# It validates functionality of cmd: ./get-sites.py -a <api> -t <token> -f <file_pathname_where_json_is_stored> -n <namespace_name> -q --log-stdout
def test_api_ns_query():
    start_time = time.perf_counter()
    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=GET_NAMESPACE, site=None, workers=WORKERS)
    q.run()
    q.write_json_file(GET_NAMESPACE_FILE)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f'Query time: {int(elapsed_time)} seconds with {WORKERS} workers')

    # Ensure file was created
    assert os.path.exists(GET_NAMESPACE_FILE), f"file {GET_NAMESPACE_FILE} was not created."

    # Validate file contents
    with open(GET_NAMESPACE_FILE, "r") as f:
        data = json.load(f)

    # Check on structure (fit actual expected structure) as well as to check if data is not empty
    assert isinstance(data, dict) or isinstance(data, list), "Output JSON is not a dict or list."
    assert len(data) > 0, "Output file is empty."

    # Clean up file where retrieved json is stored
    os.remove(GET_NAMESPACE_FILE)


# This test verifies the inventory functionality using the json_file and its path of a particular site.
# It validates the cmd: ./get-sites.py -a <api> -t <token> -f <filepath_where_json_of_required_site_is_present> --build-inventory --inventory-table --inventory-file-csv <filepath_where_csv_of_obtained_inventory_data_is_to_be_stored> --log-stdout
def test_api_inventory_function(caplog):
    caplog.set_level(logging.INFO)  # Capture INFO logs

    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=None, site=None, workers=WORKERS)

    # retrieving inventory data, asserting if it is not empty and writing data to inventory csv_file
    data = q.build_inventory(json_file=TEST_DATA_SITE_OLD_FILE_NAME_REPLICA)
    assert data is not None, "Inventory data is None"
    if data:
        q.write_string_file(INVENTORY_FILE_CSV, data.get_csv_string())
        logger.info(f"\n\n{data.get_formatted_string('text')}\n")

    # Ensure file was created
    assert os.path.exists(INVENTORY_FILE_CSV), f"file {INVENTORY_FILE_CSV} was not created."

    # Validate file contents
    with open(INVENTORY_FILE_CSV, "r") as f:
        csv_content = f.read()

    # checking if the desired words are present in the both the csv_file as well as inventory_table logged to stdout
    EXPECTED_WORDS = ["kind", "spec", "node"]

    for word in EXPECTED_WORDS:
        assert word in csv_content, f"'{word}' not found in CSV content"

    # Assert pretty table (log) contains expected words
    log_output = caplog.text
    for word in EXPECTED_WORDS:
        assert word in log_output, f"'{word}' not found in log output (pretty table)"

    # Clean up file where obtained inventory csv is stored
    os.remove(INVENTORY_FILE_CSV)


# This test verifies the compariso functionality using the json_files of the sites to be compared
# It validates the cmd: ./get-sites.py -a <api> -t <token> -c --old-site <site1_name> --old-site-file <filepath_where_json_of_site1_is_present> --new-site <site2_name> --new-site-file <filepath_where_json_of_site2_is_present> --diff-table --diff-file-csv <filepath_where_compared_diff_is_to_be_written> --log-stdout
def test_api_compare_function(caplog):
    caplog.set_level(logging.INFO)  # Capture INFO logs

    # Here both sites being compared should be of same kind or smv-smv2 duo (eg: aws_vpc_site canot be compared with securemesh_site, securemesh_site can be compared with securemesh_site_v2)
    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=None, site=None, workers=WORKERS)

    # retrieving data, asserting if data is not empty or not and logging and writing data to diff csv_file
    data = q.compare(old_site=TEST_DATA_SITE_OLD_NAME, old_file=TEST_DATA_SITE_OLD_FILE_NAME_2,
                     new_site=TEST_DATA_SITE_NEW_NAME, new_file=TEST_DATA_SITE_NEW_FILE_NAME_2)
    assert data is not None, "Comparison data is None"
    if data:
        q.write_string_file(DIFF_FILE_CSV, data.get_csv_string())
        logger.info(f"\n\n{data.get_formatted_string('text')}\n")

    # checking if obtained data is prettytable and the field_names of the table are the ones given
    assert isinstance(data, PrettyTable), "not pretty table"
    assert data.field_names == ["path", "values"], "expected field-names not present"

    # Ensure diff csv_file was created
    assert os.path.exists(DIFF_FILE_CSV), f"file {DIFF_FILE_CSV} was not created."

    # Read csv_file contents
    with open(DIFF_FILE_CSV, "r") as f:
        csv_content = f.read()

    # Ensure if expected words are present in csv_content retrieved from file as well as in the pretty_table in stdout.
    # Since names of comparing sites are mostly different, they key will mostly be present in comparison output.
    EXPECTED_WORDS = ["metadata/name"]

    for word in EXPECTED_WORDS:
        assert word in csv_content, f"'{word}' not found in CSV content"

    # Assert pretty table (log) contains expected words
    log_output = caplog.text
    for word in EXPECTED_WORDS:
        assert word in log_output, f"'{word}' not found in log output (pretty table)"

    # Clean up csv_file where diff data is stored
    os.remove(DIFF_FILE_CSV)


# fixture to return the json_content of the json_file of the site1 retrieved using query functionality
@pytest.fixture
def data_old():
    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=None, site=None, workers=WORKERS)
    return q.read_json_file(TEST_DATA_SITE_OLD_FILE_NAME_2)


# fixture to return the name of site1
@pytest.fixture
def old_site():
    return TEST_DATA_SITE_OLD_NAME


# fixture to return dict_keys which are used to get the values from the site json query file
@pytest.fixture
def dict_keys():
    return ['kind', 'metadata/name', 'spec/vip_vrrp_mode', 'spec/site_to_site_ipsec_connectivity',
            'spec/main_nodes/0/name', 'spec/main_nodes/0/slo_address', 'spec/proactive_monitoring',
            'nodes/node0/hw_info/memory/speed', 'nodes/node0/interfaces', 'namespaces/jeevan-ns/loadbalancer/http',
            'namespaces/default/origin_pools', 'bgp', 'None/worker_node_count']


# test to verify if the below parameterized values match with the ones present in the site json file (obtained using query by site) using the dict_keys as keys
@pytest.mark.parametrize("expected", [
    [
        ['securemesh_site'],
        ['smeshsiteongoing-singlenode'],
        ['VIP_VRRP_INVALID'],
        [[{'destination': ['10.144.11.158'], 'port': 0}]],
        ['master-0'],
        ['10.144.11.158'],
        [],
        [],
        ['eth1', 'eth2'],
        ['jeevan', 'jeevan-1', 'port-range'],
        ['gnu-on-ce'],
        ['ves-io-bgp-ves-io-securemesh-site-smeshsiteongoing-singlenode'],
        [],
    ]
])
def test_verify_get_by_path(dict_keys, expected, old_site, data_old):
    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=None, site=None, workers=WORKERS)

    for idx, k in enumerate(dict_keys):
        response = list()
        result = q._get_by_path(data_old['site'][old_site], k.split("/"), response)
        assert result == expected[idx]


# fixture to return the dict_keys against which the ones in compared output are verified
@pytest.fixture
def dict_keys_new():
    return ['kind', 'main_node_count', 'metadata/name', 'metadata/labels/host-os-version', 'metadata/labels/hw-model',
            'metadata/labels/hw-vendor', 'metadata/labels/hw-version', 'metadata/labels/test-feature',
            'metadata/labels/ves.io/provider', 'metadata/labels/chaos-test', 'metadata/labels/public-ip',
            'metadata/labels/site-mesh-group-type', 'metadata/labels/smv2-smg-fullmesh-public-auto',
            'metadata/labels/test-feature-automation', 'metadata/labels/ver-type', 'metadata/labels/waap-on-smsv2',
            'metadata/labels/iperf-test', 'metadata/labels/ms-smg', 'metadata/labels/name', 'metadata/labels/purpose',
            'metadata/labels/single-ver', 'metadata/labels/smeshongoing', 'metadata/description', 'spec/address',
            'spec/volterra_software_version', 'spec/connected_re/0/uid', 'spec/connected_re/0/name',
            'spec/connected_re/1/uid', 'spec/connected_re/1/name', 'spec/connected_re_for_config/0/uid',
            'spec/connected_re_for_config/0/name', 'spec/vip_vrrp_mode', 'spec/tunnel_type',
            'spec/operating_system_version', 'spec/region', 'spec/site_to_site_ipsec_connectivity',
            'spec/main_nodes/2/name', 'spec/main_nodes/2/slo_address', 'spec/admin_user_credentials',
            'spec/proactive_monitoring', 'nodes/node0/hostname', 'nodes/node0/hw_info/os/name',
            'nodes/node0/hw_info/os/version', 'nodes/node0/hw_info/os/release', 'nodes/node0/hw_info/product/name',
            'nodes/node0/hw_info/product/vendor', 'nodes/node0/hw_info/product/version',
            'nodes/node0/hw_info/board/vendor', 'nodes/node0/hw_info/chassis/vendor',
            'nodes/node0/hw_info/chassis/version', 'nodes/node0/hw_info/bios/vendor',
            'nodes/node0/hw_info/bios/version', 'nodes/node0/hw_info/bios/date', 'nodes/node0/hw_info/cpu/model',
            'nodes/node0/hw_info/cpu/speed', 'nodes/node0/hw_info/cpu/cache', 'nodes/node0/hw_info/cpu/flags',
            'nodes/node0/hw_info/memory/type', 'nodes/node0/hw_info/memory/speed', 'nodes/node0/hw_info/memory/size_mb',
            'nodes/node0/hw_info/storage/0/name', 'nodes/node0/hw_info/storage/0/driver',
            'nodes/node0/hw_info/storage/0/model', 'nodes/node0/hw_info/storage/0/size_gb',
            'nodes/node0/hw_info/network', 'nodes/node0/hw_info/kernel/release', 'nodes/node0/hw_info/kernel/version',
            'nodes/node0/hw_info/usb', 'nodes/node0/interfaces', 'nodes/node1/hostname', 'nodes/node1/hw_info/os/name',
            'nodes/node1/hw_info/os/vendor', 'nodes/node1/hw_info/os/version', 'nodes/node1/hw_info/os/release',
            'nodes/node1/hw_info/os/architecture', 'nodes/node1/hw_info/product/name',
            'nodes/node1/hw_info/product/vendor', 'nodes/node1/hw_info/product/version',
            'nodes/node1/hw_info/board/name', 'nodes/node1/hw_info/board/vendor', 'nodes/node1/hw_info/board/version',
            'nodes/node1/hw_info/chassis/type', 'nodes/node1/hw_info/chassis/vendor',
            'nodes/node1/hw_info/chassis/version', 'nodes/node1/hw_info/bios/vendor',
            'nodes/node1/hw_info/bios/version', 'nodes/node1/hw_info/bios/date', 'nodes/node1/hw_info/cpu/vendor',
            'nodes/node1/hw_info/cpu/model', 'nodes/node1/hw_info/cpu/speed', 'nodes/node1/hw_info/cpu/cache',
            'nodes/node1/hw_info/cpu/cpus', 'nodes/node1/hw_info/cpu/cores', 'nodes/node1/hw_info/cpu/threads',
            'nodes/node1/hw_info/cpu/flags', 'nodes/node1/hw_info/memory/type', 'nodes/node1/hw_info/memory/speed',
            'nodes/node1/hw_info/memory/size_mb', 'nodes/node1/hw_info/storage', 'nodes/node1/hw_info/network',
            'nodes/node1/hw_info/kernel/release', 'nodes/node1/hw_info/kernel/version',
            'nodes/node1/hw_info/kernel/architecture', 'nodes/node1/hw_info/usb', 'nodes/node1/hw_info/numa_nodes',
            'nodes/node2/hostname', 'nodes/node2/hw_info/os/name', 'nodes/node2/hw_info/os/vendor',
            'nodes/node2/hw_info/os/version', 'nodes/node2/hw_info/os/release', 'nodes/node2/hw_info/os/architecture',
            'nodes/node2/hw_info/product/name', 'nodes/node2/hw_info/product/vendor',
            'nodes/node2/hw_info/product/version', 'nodes/node2/hw_info/board/name', 'nodes/node2/hw_info/board/vendor',
            'nodes/node2/hw_info/board/version', 'nodes/node2/hw_info/chassis/type',
            'nodes/node2/hw_info/chassis/vendor', 'nodes/node2/hw_info/chassis/version',
            'nodes/node2/hw_info/bios/vendor', 'nodes/node2/hw_info/bios/version', 'nodes/node2/hw_info/bios/date',
            'nodes/node2/hw_info/cpu/vendor', 'nodes/node2/hw_info/cpu/model', 'nodes/node2/hw_info/cpu/speed',
            'nodes/node2/hw_info/cpu/cache', 'nodes/node2/hw_info/cpu/cpus', 'nodes/node2/hw_info/cpu/cores',
            'nodes/node2/hw_info/cpu/threads', 'nodes/node2/hw_info/cpu/flags', 'nodes/node2/hw_info/memory/type',
            'nodes/node2/hw_info/memory/speed', 'nodes/node2/hw_info/memory/size_mb', 'nodes/node2/hw_info/storage',
            'nodes/node2/hw_info/network', 'nodes/node2/hw_info/kernel/release', 'nodes/node2/hw_info/kernel/version',
            'nodes/node2/hw_info/kernel/architecture', 'nodes/node2/hw_info/usb', 'nodes/node2/hw_info/numa_nodes',
            'namespaces', 'bgp', 'None/worker_node_count']


# fixture to return the json_content of the site2
@pytest.fixture
def data_new():
    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=None, site=None, workers=WORKERS)
    return q.read_json_file(TEST_DATA_SITE_NEW_FILE_NAME_2)


# fixture to return the name of the site2
@pytest.fixture
def new_site():
    return TEST_DATA_SITE_NEW_NAME


# Tc to check if the keys of comparison table are as expected to verify if right set of keys are retrieved in comparison
def test_verify_get_keys(dict_keys_new, old_site, data_old, new_site, data_new):
    q = Api(logger=logger, api_url=API_URL, api_token=API_TOKEN, namespace=None, site=None, workers=WORKERS)

    # The below diff is commented as the output of it is directly given above as parameterized.
    compared1 = diff(data_old['site'][old_site], data_new['site'][new_site], syntax="compact")
    r = []

    assert q._get_keys(None, compared1, r, old_site, data_old) == dict_keys_new
