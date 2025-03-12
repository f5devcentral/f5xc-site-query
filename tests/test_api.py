import json
from unittest.mock import patch

import jsondiff.symbols
from prettytable import PrettyTable

import pytest
import logging

from lib.api import Api

API_URL = "https://playground.console.ves.volterra.io/api"
API_TOKEN = "abc123456789"
WORKERS = 10
USER_SPECIFIED_SITE = "f5xc-aws-ce-test-60"
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


@pytest.fixture
def data_old(api):
    return api.read_json_file(TEST_DATA_SITE_OLD_FILE_NAME)


@pytest.fixture
def old_site():
    return TEST_DATA_SITE_OLD_NAME


@pytest.fixture
def dict_keys():
    return ['kind', 'metadata/name', 'spec/vip_vrrp_mode', 'spec/site_to_site_ipsec_connectivity', 'spec/main_nodes/0/name', 'spec/main_nodes/0/slo_address', 'spec/main_nodes/1/name', 'spec/main_nodes/1/slo_address',
            'spec/main_nodes/2/name', 'spec/main_nodes/2/slo_address', 'spec/proactive_monitoring', 'nodes/node0/hw_info/memory/speed', 'nodes/node0/interfaces', 'nodes/node1/interfaces', 'nodes/node2/interfaces',
            'namespaces/pg-vsite-testing/proxys', 'namespaces/pg-vsite-testing/loadbalancer/http', 'namespaces/pg-vsite-testing/loadbalancer/tcp', 'namespaces/pg-vsite-testing/origin_pools', 'bgp', 'None/worker_node_count']


@pytest.mark.parametrize("compared", [
    {'kind': 'securemesh_site_v2', 'metadata': {'name': 'f5xc-aws-ce-test-61', 'labels': {'hw-serial-number': 'ec2a4ade-2eef-8f87-ff02-97a11c6aac36'}},
     'spec': {'vip_vrrp_mode': 'VIP_VRRP_DISABLE', 'site_to_site_ipsec_connectivity': [], 'main_nodes': {0: {'name': 'ip-192-168-0-24', 'slo_address': '192.168.0.24'}, 1: {'name': 'ip-192-168-0-44', 'slo_address': '192.168.0.44'}, 2: {'name': 'ip-192-168-0-69', 'slo_address': '192.168.0.69'}}, 'proactive_monitoring': {jsondiff.symbols.replace: {'proactive_monitoring_enable': {}}}},
     'sms': {'metadata': {'name': 'f5xc-aws-ce-test-61', 'labels': {'hw-serial-number': 'ec2a4ade-2eef-8f87-ff02-97a11c6aac36'}},
             'spec': {'active_enhanced_firewall_policies': {'enhanced_firewall_policies': [{'name': 'test123', 'namespace': 'system', 'tenant': 'playground-urxgwtyy'}, {'name': 'test124', 'namespace': 'system', 'tenant': 'playground-urxgwtyy'}]}, 'active_forward_proxy_policies': {'forward_proxy_policies': [{'name': 'pg-proxy', 'namespace': 'system', 'tenant': 'playground-urxgwtyy'}]}, 'admin_user_credentials': None, 'aws': {'not_managed': {'node_list': []}}, 'block_all_services': {},
                      'dc_cluster_group_slo': {'name': 'pg-dccg', 'namespace': 'system', 'tenant': 'playground-urxgwtyy'}, 'dns_ntp_config': {'f5_dns_default': {}, 'f5_ntp_default': {}}, 'load_balancing': {'vip_vrrp_mode': 'VIP_VRRP_DISABLE'}, 'local_vrf': {'default_config': {}, 'default_sli_config': {}}, 'no_s2s_connectivity_sli': {}, 'proactive_monitoring': {'proactive_monitoring_enable': {}}, 're_select': {'geo_proximity': {}},
                      'software_settings': {'os': {'default_os_version': {}}, 'sw': {'default_sw_version': {}}}, 'tunnel_dead_timeout': 0, 'tunnel_type': 'SITE_TO_SITE_TUNNEL_IPSEC_OR_SSL', 'upgrade_settings': {'kubernetes_upgrade_drain': {'enable_upgrade_drain': {'disable_vega_upgrade_mode': {}, 'drain_max_unavailable_node_count': 1, 'drain_node_timeout': 300}}},
                      jsondiff.symbols.delete: ['volterra_certified_hw', 'master_node_configuration', 'worker_nodes', 'no_bond_devices', 'custom_network_config', 'address', 'coordinates', 'default_blocked_services', 'kubernetes_upgrade_drain']}},
     'nodes': {'node0': {'hw_info': {'product': {'serial': 'ec21783d-9341-01e3-717a-63e4c4842a78'}, 'board': {'asset_tag': 'i-0c2e3027e9a11f243'}, 'memory': {'speed': 3200}, 'storage': {0: {'serial': 'vol0f41451d44f7ab696'}, 1: {'serial': 'vol045ab3f38d518039c'}}}, jsondiff.symbols.delete: ['interfaces']},
               'node1': {'hw_info': {'product': {'serial': 'ec229b0b-9a51-f638-5aaa-b7d17c7dae67'}, 'board': {'asset_tag': 'i-0843aea49b4d27037'}, 'storage': {0: {'serial': 'vol007f302465c9a9106'}, 1: {'serial': 'vol0ddcfa0bd0880b7e5'}}}, jsondiff.symbols.delete: ['interfaces']},
               'node2': {'hw_info': {'product': {'serial': 'ec2a4ade-2eef-8f87-ff02-97a11c6aac36'}, 'board': {'asset_tag': 'i-06e5337afb8531822'}, 'storage': {0: {'serial': 'vol0f8e2e4ac92126bd5'}, 1: {'serial': 'vol089f12bedaade8363'}}}, jsondiff.symbols.delete: ['interfaces']}}, 'namespaces': {'pg-vsite-testing': {'proxys': {jsondiff.symbols.replace: {
        'test125': {'spec': {'http_proxy': {'enable_http': {}, 'more_option': None}, 'site_virtual_sites': {'advertise_where': [{'site': {'network': 'SITE_NETWORK_INSIDE', 'site': {'tenant': 'playground-urxgwtyy', 'namespace': 'system', 'name': 'f5xc-aws-ce-test-61'}, 'ip': '', 'ipv6': ''}, 'use_default_port': {}}]}, 'site_local_network': {}, 'no_forward_proxy_policy': {}, 'no_interception': {}, 'connection_timeout': 2000},
                    'metadata': {'name': 'test125', 'namespace': 'pg-vsite-testing', 'labels': {}, 'annotations': {}, 'description': '', 'disable': False},
                    'system_metadata': {'uid': '696c630d-2dba-403c-a2af-22d7c585fcf0', 'creation_timestamp': '2025-03-05T15:12:39.926974737Z', 'deletion_timestamp': None, 'modification_timestamp': None, 'initializers': None, 'finalizers': [], 'tenant': 'playground-urxgwtyy', 'creator_class': 'prism', 'creator_id': 't.test@ves.io', 'object_index': 0, 'owner_view': None, 'labels': {}}}}}, jsondiff.symbols.delete: ['loadbalancer', 'origin_pools']}}, 'bgp': {jsondiff.symbols.replace: {
        'ves-io-bgp-ves-io-securemesh-site-v2-f5xc-aws-ce-test-61': {'spec': {'where': {'site': {'ref': [{'kind': 'site', 'uid': '', 'tenant': 'playground-urxgwtyy', 'namespace': 'system', 'name': 'f5xc-aws-ce-test-61'}], 'network_type': 'VIRTUAL_NETWORK_SITE_LOCAL', 'disable_internet_vip': {}, 'refs': []}}, 'bgp_parameters': {'asn': 64513, 'local_address': {}, 'bgp_router_id_type': 'BGP_ROUTER_ID_FROM_INTERFACE', 'bgp_router_id': None, 'bgp_router_id_key': ''}, 'peers': []},
                                                                     'metadata': {'name': 'ves-io-bgp-ves-io-securemesh-site-v2-f5xc-aws-ce-test-61', 'namespace': 'system', 'labels': {}, 'annotations': {}, 'description': '', 'disable': False},
                                                                     'system_metadata': {'uid': '2354e90e-02e5-45a0-bc15-212a0a39f2da', 'creation_timestamp': '2025-03-03T10:57:56.733250025Z', 'deletion_timestamp': None, 'modification_timestamp': '2025-03-06T02:58:26.329895787Z', 'initializers': None, 'finalizers': [], 'tenant': 'playground-urxgwtyy', 'creator_class': 'akar', 'creator_id': '', 'object_index': 0,
                                                                                         'owner_view': {'kind': 'fleet', 'uid': 'c8ca6bfc-d269-4b5a-b226-23e8efab5494', 'namespace': 'system', 'name': 'ves-io-securemesh-site-v2-f5xc-aws-ce-test-61'}, 'labels': {}}}}}, jsondiff.symbols.delete: ['worker_node_count']},
])
def test_get_keys(api, compared, dict_keys, old_site, data_old):
    r = []
    assert api._get_keys(None, compared, r, old_site, data_old) == dict_keys


@pytest.mark.parametrize("expected", [
    [
        ['securemesh_site'],
        ['f5xc-aws-ce-test-60'],
        ['VIP_VRRP_ENABLE'],
        [[{'destination': ['192.168.0.16'], 'port': 0}, {'destination': ['192.168.0.37'], 'port': 0}, {'destination': ['192.168.0.88'], 'port': 0}]],
        ['ip-192-168-0-16'],
        ['192.168.0.16'],
        ['ip-192-168-0-37'],
        ['192.168.0.37'],
        ['ip-192-168-0-88'],
        ['192.168.0.88'],
        [],
        [2666],
        ['eth0', 'eth1'],
        ['eth0', 'eth1'],
        ['eth0', 'eth1'],
        ['test123', 'test124'],
        ['pg-vsite-prv'],
        ['pg-private-tcp-lb'],
        ['pg-vsite-private-dc-pool'],
        ['ves-io-bgp-ves-io-securemesh-site-f5xc-aws-ce-test-60'],
        [],
    ]
])
def test_get_by_path(api, dict_keys, expected, old_site, data_old):
    for idx, k in enumerate(dict_keys):
        response = list()
        result = api._get_by_path(data_old['site'][old_site], k.split("/"), response)
        assert result == expected[idx]
