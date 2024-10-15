# f5xc-site-query

Helper tool get-sites.py queries application objects (HTTP and TCP Load Balancers, Proxys and Origin Pools) for a given namespace
(or across all namespaces) and creates a dictionary with all objects listed per site and virtual site.

## Install 
1. Create a Python Virtual Environment.
   `python3 -m venv myenv`
2. Source the new environment.
    `source myenv/bin/activate`
3. Install required python modules.
   `python3 -m pip install -r requirements.txt`

## Config Setup Instructions

1. Create an API Token for our Tenant. 
   Sign into the F5 XC Console with Administrative privileges and navigate to Administration. Under 'Personal Management' select 'Credentials'. Then click 'Add Credentials' and populate the window. Make sure to select 'API Token' as the 'Credential Type' field. Save the generated API Token for the next step.

## Usage

Define environment variables

```
export f5xc_api_url="https://<tenant>.console.ves.volterra.io/api"
export f5xc_api_token="............................"
```




