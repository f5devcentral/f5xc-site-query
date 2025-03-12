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
URI_F5XC_ENHANCED_FW_POLICIES = "/config/namespaces/{namespace}/enhanced_firewall_policys"
URI_F5XC_FORWARD_PROXY_POLICY = "/config/namespaces/{namespace}/forward_proxy_policys/{name}"

#
# F5XC objects
#
F5XC_SITE_TYPES = ["site", "virtual_site"]  # "virtual_site_with_vip"
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

#
# Site query
#
API_PROCESSORS = ["site", "vs", "lb", "proxy", "originpool", "bgp", "smg", "cloudconnect", "segment"]
PROCESSOR_PACKAGE = "lib.processor"
CSV_EXPORT_KEYS = ["spec", "efp", "fpp", "bgp", "smg", "spoke", "segments", "dc_cluster_group", "nodes", "namespaces"]
EXCLUDE_COMPARE_ATTRIBUTES = ["serial", "asset_tag", "hw-serial-number", "spec/site_to_site_ipsec_connectivity"]
SITE_OBJECT_TYPE_SMS = "sms"
SITE_OBJECT_TYPE_LEGACY = "legacy"
SITE_OBJECT_PROCESSORS = ["site_details", "efp", "fpp", "dc_cluster_group", "cloudlink", "node_interfaces", "hw_info", "spokes"]
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
