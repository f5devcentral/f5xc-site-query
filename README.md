# f5xc-site-query sequential version

## Overview

Helper tool get-sites.py queries application objects (HTTP and TCP Load Balancers, Proxys and Origin Pools) per namespace
(or all namespaces) and creates a json file with all objects listed per site, virtual site and namespace.

The generated get-sites.json file helps to answer questions like

a) What application objects are assigned to a site or virtual site and in what namespace
b) Who created an application object
c) Are there sites that only serve origin pools
d) Are there application objects assigned to non-existent sites

## Installation

1. Create a Python Virtual Environment:
   `python3 -m venv myenv`

2. Source the new environment:
    `source myenv/bin/activate`

3. Install required python modules:
   `python3 -m pip install -r requirements.txt`

## Credentials

The script uses a F5XC API Token to access a Tenant's configuration.

1. Create an API Token for our Tenant:

   Sign in to the F5 XC Console with Administrative privileges and navigate to Administration. Under 'Personal Management' select 'Credentials'. 
   Then click 'Add Credentials' and populate the window. Make sure to select 'API Token' as the 'Credential Type' field. Save the generated API Token for the next step.

2. Define environment variables

Set environment variables with the API URL (replace tenant with your tenant name) and the generated API Token. 

```
export f5xc_api_url="https://<tenant>.console.ves.volterra.io/api"
export f5xc_api_token="............................"
```

Alternatively you can set command line options instead when running the script:

```
./get-sites.py -t f5xc_api_token -a https://<tenant>.console.ves.volterra.io/api
```

## Usage

Launched without any options will query application objects and site information for the default namespace. Alternatively a specific namespace
can be requested via `-n <namespace>` option. To walk thru all namespaces, use `-n ''`, expect this to take several minutes depending on the 
number of existing namespaces.

While running, the script prints out the namespace, object and site to stderr:

```
$ ./get-sites.py 
namespace default loadbalancer f5dc-hello site alt-reg-site
namespace default loadbalancer f5dc-hello-cluster2 site f5dc-wdc-2-sat-cluster-2
namespace default loadbalancer test site aws-tgw-site
namespace default loadbalancer camera-default site smartretail-isv
namespace default loadbalancer f5dc-cluster2-iperf3 site f5dc-wdc-2-sat-cluster-2
namespace default loadbalancer mw-test site aws-tgw-site
namespace default proxys abc site bhu-appstack
namespace default origin_pools byerly-pool site byerly-twg
namespace default origin_pools camera-1 site smartretail-isv
namespace default origin_pools f5dc-cluster1-iperf3 site f5dc-wdc-1-sat-cluster-1
namespace default origin_pools f5dc-hello site f5dc-wdc-1-sat-cluster-1
namespace default origin_pools f5os-demo-pool site f5os-demo2-site
namespace default origin_pools mgala-aws-ubuntu-sms site mgala-sms-demo2
namespace default origin_pools mw-test site alt-reg-site
namespace default origin_pools mwce1-alpine1 site mw-ce1
namespace default origin_pools xcdf-test site data-fabric-on-xc-a2-gpu
11 sites and 0 virtual sites written to get-sites.json

Sites with only origin pools: []
```

The generated get-sites.json is now populated with application objects per namespace and site/virtual site and can be parsed
e.g. using `gron` or inspected visually.

We can now answer the questions asked in the Overview section above:

a) What application objects are assigned to a site or virtual site and in what namespace

```
{
  "namespaces": [
    "default"
  ],
  "site": {
    "alt-reg-site": {
      "default": {
        "loadbalancer": {
          "f5dc-hello": {
            "uid": "869d61fa-0b21-4482-8d8d-14ca18aa2880",
            "creation_timestamp": "2022-05-10T10:11:18.812992075Z",
            "deletion_timestamp": null,
            "modification_timestamp": "2024-09-12T08:48:52.478785492Z",
            "initializers": null,
            "finalizers": [],
            "tenant": "playground-wtppvaog",
            "creator_class": "prism",
            "creator_id": "m.wiget@f5.com",
            "object_index": 0,
            "owner_view": null,
            "labels": {}
          }
        },
        "origin_pools": {
          "mw-test": {
            "uid": "3c5cb595-a78a-4edf-9c95-9d3dedbeea37",
            "creation_timestamp": "2024-09-14T12:20:25.295967722Z",
            "deletion_timestamp": null,
            "modification_timestamp": null,
            "initializers": null,
            "finalizers": [],
            "tenant": "playground-wtppvaog",
            "creator_class": "prism",
            "creator_id": "m.wiget@f5.com",
            "object_index": 0,
            "owner_view": null,
            "labels": {}
          }
        }
      },
      "site_labels": {}
    },
    . . .
```

The site `alt-reg-site` has a loadbalancer f5dc-hello and origin pool `mw-test` assigned. Empty `site_labels` for this 
site `alt-reg-site` indicates the site no longer exists.

b) Who created an application object

To get objects created by a specific creator (F5XC account), use `gron` and `grep`:

```
$ gron get-sites.json | grep wiget
json.site["alt-reg-site"]["default"].loadbalancer["f5dc-hello"].creator_id = "m.wiget@f5.com";
json.site["alt-reg-site"]["default"].origin_pools["mw-test"].creator_id = "m.wiget@f5.com";
json.site["aws-tgw-site"]["default"].loadbalancer["mw-test"].creator_id = "m.wiget@f5.com";
json.site["f5dc-wdc-1-sat-cluster-1"]["default"].origin_pools["f5dc-cluster1-iperf3"].creator_id = "m.wiget@f5.com";
json.site["f5dc-wdc-1-sat-cluster-1"]["default"].origin_pools["f5dc-hello"].creator_id = "m.wiget@f5.com";
json.site["f5dc-wdc-2-sat-cluster-2"]["default"].loadbalancer["f5dc-cluster2-iperf3"].creator_id = "m.wiget@f5.com";
json.site["f5dc-wdc-2-sat-cluster-2"]["default"].loadbalancer["f5dc-hello-cluster2"].creator_id = "m.wiget@f5.com";
json.site["mw-ce1"]["default"].origin_pools["mwce1-alpine1"].creator_id = "m.wiget@f5.com";
```

To narrow the search down to a single site, use:

```
$ gron get-sites.json | grep wiget | grep f5dc-wdc-1-sat-cluster-1
json.site["f5dc-wdc-1-sat-cluster-1"]["default"].origin_pools["f5dc-cluster1-iperf3"].creator_id = "m.wiget@f5.com";
json.site["f5dc-wdc-1-sat-cluster-1"]["default"].origin_pools["f5dc-hello"].creator_id = "m.wiget@f5.com";
```

c) Are there sites that only serve origin pools

After collecting all configuration objects into the sites dictionary, the script walks the dictionary and checks
for sites that have only load balancers and stores the result as a separate list in sites under `sites_with_only_origin_pools`.
To extract that list, look at the written get-sites.json file or use `gron` and `grep`:

```
$ gron get-sites.json|grep with_only
json.sites_with_only_origin_pools = [];
json.sites_with_only_origin_pools[2] = "ce-on-k8s-aswin-aws";
json.sites_with_only_origin_pools[3] = "ce-rseries-demo";
json.sites_with_only_origin_pools[4] = "crt-ce05";
json.sites_with_only_origin_pools[5] = "auto-az-crt";
json.sites_with_only_origin_pools[6] = "cosmos-ce-hyd-cloud";
json.sites_with_only_origin_pools[9] = "multitunnel-aws";
json.sites_with_only_origin_pools[10] = "auto-aws-crt";
json.sites_with_only_origin_pools[11] = "ce-rseries-integration";
```

d) Are there application objects assigned to non-existent sites

Look through the generated get-sites.json file for empty site_labels. See answer `a)` above.






