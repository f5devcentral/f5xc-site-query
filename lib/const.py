#
# URIs
#
URI_F5XC_BGP = "/config/namespaces/{namespace}/bgps/{name}"
URI_F5XC_BGPS = "/config/namespaces/{namespace}/bgps"
URI_F5XC_SITE = "/config/namespaces/{namespace}/sites/{name}"
URI_F5XC_SITES = "/config/namespaces/system/sites"
URI_F5XC_SMS_V1 = "/config/namespaces/{namespace}/securemesh_sites/{name}"
URI_F5XC_SMS_V2 = "/config/namespaces/{namespace}/securemesh_site_v2s/{name}"
URI_F5XC_PROXIES = "/config/namespaces/{namespace}/proxys"
URI_F5XC_SEGMENT = "/config/namespaces/{namespace}/segments/{name}"
URI_F5XC_SEGMENTS = "/config/namespaces/{namespace}/segments"
URI_F5XC_NAMESPACE = "/web/namespaces"
URI_F5XC_CLOUD_LINK = "/config/namespaces/{namespace}/cloud_links/{name}"
URI_F5XC_CLOUD_LINKS = "/config/namespaces/{namespace}/cloud_links"
URI_F5XC_SITE_AWS_VPC = "/config/namespaces/{namespace}/aws_vpc_sites/{name}"
URI_F5XC_SITE_AWS_TGW = "/config/namespaces/{namespace}/aws_tgw_sites/{name}"
URI_F5XC_SITE_GCP_VPC = "/config/namespaces/{namespace}/gcp_vpc_sites/{name}"
URI_F5XC_VIRTUAL_SITE = "/config/namespaces/{namespace}/virtual_sites/{name}"
URI_F5XC_ORIGIN_POOLS = "/config/namespaces/{namespace}/origin_pools"
URI_F5XC_VIRTUAL_SITES = "/config/namespaces/{namespace}/virtual_sites"
URI_F5XC_CLOUD_CONNECT = "/config/namespaces/{namespace}/cloud_connects/{name}"
URI_F5XC_LOAD_BALANCER = "/config/namespaces/{namespace}/{lb_type}"
URI_F5XC_CLOUD_CONNECTS = "/config/namespaces/{namespace}/cloud_connects"
URI_F5XC_SITE_VOLT_STACK = "/config/namespaces/{namespace}/voltstack_sites/{name}"
URI_F5XC_SITE_AZURE_VNET = "/config/namespaces/{namespace}/azure_vnet_sites/{name}"
URI_F5XC_SITE_MESH_GROUP = "/config/namespaces/{namespace}/site_mesh_groups/{name}"
URI_F5XC_SITE_MESH_GROUPS = "/config/namespaces/{namespace}/site_mesh_groups"
URI_F5XC_DC_CLUSTER_GROUP = "/config/namespaces/{namespace}/dc_cluster_groups/{name}"
URI_F5XC_ENHANCED_FW_POLICY = "/config/namespaces/{namespace}/enhanced_firewall_policys/{name}"
URI_F5XC_FIREWALL_FAST_ACLS = "/config/namespaces/{namespace}/fast_acls"
URI_F5XC_ENHANCED_FW_POLICIES = "/config/namespaces/{namespace}/enhanced_firewall_policys"
URI_F5XC_FORWARD_PROXY_POLICY = "/config/namespaces/{namespace}/forward_proxy_policys/{name}"

#
# F5XC objects
#
F5XC_SITE = "site"
F5XC_VIRTUAL_SITE = "virtual_site"
F5XC_SITE_TYPES = [F5XC_SITE, F5XC_VIRTUAL_SITE]  # "virtual_site_with_vip"
F5XC_SITE_VOLT_STACK = "voltstack_site"
F5XC_SITE_TYPE_SMS_V1 = "securemesh_site"
F5XC_SITE_TYPE_SMS_V2 = "securemesh_site_v2"
F5XC_SITE_TYPE_AWS_VPC = "aws_vpc_site"
F5XC_SITE_TYPE_AWS_TGW = "aws_tgw_site"
F5XC_SITE_TYPE_GCP_VPC = "gcp_vpc_site"
F5XC_SITE_TYPE_APP_STACK = "appstack"
F5XC_SITE_TYPE_AZURE_VNET = "azure_vnet_site"
F5XC_NODE_PRIMARY = "k8s-master-primary"
F5XC_NAMESPACE_SYSTEM = "system"
F5XC_NAMESPACE_SHARED = "shared"
F5XC_LOAD_BALANCER_TYPES = ["http_loadbalancers", "tcp_loadbalancers", "udp_loadbalancers"]
F5XC_ORIGIN_SERVER_TYPES = ['private_ip', 'k8s_service', 'consul_service', 'private_name']
F5XC_CLOUD_CONNECT_TYPES = ["azure_vnet_site", "aws_tgw_site"]
F5XC_SITE_INTERFACE_MODES = ["ingress_gw", "ingress_egress_gw"]
F5XC_CREATOR_CLASS_MAURICE = "maurice"
F5XC_SMV2_PROVIDERS = {"vmware", "aws", "azure", "gcp", "kvm", "oci", "nutanix", "openstack", "equinix", "baremetal"}

#
# Dict Keys
#
SITES_KEY = "sites"
NAMESPACES_KEY = "namespaces"
VIRTUAL_SITES_KEY = "virtual_sites"
SITE_VIRTUAL_SITES_KEY = "vsites"
SITE_TYPES = [SITES_KEY, VIRTUAL_SITES_KEY]

#
# Site query
#
API_PROCESSORS = ["vs", "site", "lb", "proxy", "originpool", "bgp", "smg", "cloudconnect", "segment"]
PROCESSOR_PACKAGE = "lib.processor"
INVENTORY_EXPORT_KEYS = ["spec", "efp", "fpp", "bgp", "smg", "spoke", "segments", "dc_cluster_group", "nodes", "namespaces", "vsites"]
XLSX_SERVICE_EXPORT_KEYS = ["efp", "fpp", "bgp", "smg", "spoke", "segments", "dc_cluster_group", "namespaces", "vsites"]
XLSX_INFRASTRUCTURE_EXPORT_KEYS = ["spec", "nodes"]
COMPARE_REGEX_METADATA_LABELS = "metadata/labels/.*"
COMPARE_REGEX_HW_INFO_CPU_FLAGS = "nodes/.*/hw_info/cpu/flags"
COMPARE_REGEX_HW_INFO_USB = "nodes/.*/hw_info/usb"
COMPARE_REGEX_NODES = "nodes/.*"
COMPARE_REGEX_SPEC = "spec/.*"
COMPARE_REGEX_LEGACY_KEY = "legacy"
COMPARE_REGEX_METADATA = "metadata/.*"
COMPARE_REGEX_NODE_INTERFACES_INTERFACE_SEGMENT= "nodes/.*/interfaces/1/ethernet_interface/segment_network"
COMPARE_REGEX_NODE_HW_INFO_BIOS = "nodes/.*/hw_info/bios/"
EXCLUDE_COMPARE_ATTRIBUTES = ["serial", "asset_tag", "hw-serial-number", "spec/site_to_site_ipsec_connectivity", COMPARE_REGEX_HW_INFO_USB, COMPARE_REGEX_HW_INFO_CPU_FLAGS,
                              COMPARE_REGEX_NODE_INTERFACES_INTERFACE_SEGMENT, COMPARE_REGEX_NODE_HW_INFO_BIOS, COMPARE_REGEX_LEGACY_KEY]
SITE_OBJECT_TYPE_SMS = "sms"
SITE_OBJECT_TYPE_LEGACY = "legacy"
SITE_OBJECT_PROCESSORS = ["site_details", "virtual_site", "efp", "fpp", "dc_cluster_group", "cloudlink", "node_interfaces", "hw_info", "spokes"]
SITE_TYPE_TO_URI_MAP = {
    F5XC_SITE_TYPE_SMS_V1: URI_F5XC_SMS_V1,
    F5XC_SITE_TYPE_SMS_V2: URI_F5XC_SMS_V2,
    F5XC_SITE_TYPE_AWS_VPC: URI_F5XC_SITE_AWS_VPC,
    F5XC_SITE_TYPE_AWS_TGW: URI_F5XC_SITE_AWS_TGW,
    F5XC_SITE_TYPE_GCP_VPC: URI_F5XC_SITE_GCP_VPC,
    F5XC_SITE_TYPE_AZURE_VNET: URI_F5XC_SITE_AZURE_VNET,
    F5XC_SITE_VOLT_STACK: URI_F5XC_SITE_VOLT_STACK,
}
HW_INFO_ITEMS_TO_PROCESS = {
    "os": ["vendor", "version", "release"],
    "cpu": ["model", "cpus", "cores", "threads"],
    "memory": ["speed", "size_mb"],
    "storage": ["size_gb"]
}
OBJECT_TO_KEY_MAP = {
    F5XC_SITE: SITES_KEY,
    F5XC_VIRTUAL_SITE: VIRTUAL_SITES_KEY,
}
