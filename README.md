# f5xc-site-query concurrent version

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

Alternatively you can set command line options instead when running the script.


## Usage

```
$ ./get-sites.py 
usage: get-sites.py [-h] [-a APIURL] [-f FILE] [-n NAMESPACE] [-s SITE] [-t TOKEN] [-w WORKERS] [--diff-file DIFF_FILE] [--log-level LOG_LEVEL] [--log-stdout] [--log-file]

Get F5 XC Sites command line arguments

options:
  -h, --help            show this help message and exit
  -a APIURL, --apiurl APIURL
                        F5 XC API URL
  -f FILE, --file FILE  write site list to file
  -n NAMESPACE, --namespace NAMESPACE
                        namespace (not setting this option will process all namespaces)
  -s SITE, --site SITE  site to be processed
  -t TOKEN, --token TOKEN
                        F5 XC API Token
  -w WORKERS, --workers WORKERS
                        maximum number of worker for concurrent processing
  --diff-file DIFF_FILE
                        compare to site
  --log-level LOG_LEVEL
                        set log level to INFO or DEBUG
  --log-stdout          write log info to stdout
  --log-file            write log info to file

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

Look through the generated `get-sites.json` file for empty site_labels. See answer `a)` above.

### Compare function

This tool provides a comparison function to compare page information. 
The steps to compare site information are as follows:


- Run query for `siteA` and write data to `out_site_a.json`
    ```bash
    ./get-sites.py -f `./out_site_a_json` -s `siteA` -w 16 --log-level INFO --log-stdout
    ```
- Run query for `siteB` and compare to `siteA` data
    ```bash
    ./get-sites.py -f `./out_site_b.json` -s `siteB` --diff-file `./ou_site_a_json` -w 16 --log-level INFO --log-stdout
    ``` 
- Output
    ```bash
    2024-10-22 16:11:09,129 - INFO - 1 site and 0 virtual site written to ./get-sites-diff-b.json
    2024-10-22 16:11:09,129 - INFO - compare started with data from get-sites-diff-a.json and current api run...
    2024-10-22 16:11:09,129 - INFO - 1 site and 0 virtual site read from ./get-sites-diff-a.json
    2024-10-22 16:11:09,129 - INFO - compare done with results: {'os': True, 'cpu': True, 'memory': True, 'network': [True]}
    ```
  
Above output shows there are no differences for hardware  info items __cpu__, __memory__ and __network__