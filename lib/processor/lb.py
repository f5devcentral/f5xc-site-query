import concurrent.futures
import json
from logging import Logger

from requests import Session

import lib.const as c
from lib.processor.base import Base

QUERY_STRING_LB_HTTP = "/http_loadbalancers/"
QUERY_STRING_LB_TCP = "/tcp_loadbalancers/"
QUERY_STRING_LB_UDP = "/udp_loadbalancers/"


class Lb(Base):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        """
        A class for processing site related load balancer data.
        :param session: current http session
        :param api_url: api url to connect to
        :param data: data structure to add load balancer data to
        :param site: user injected site name to filter for
        :param workers: amount of concurrent threads
        :param logger: log instance for writing / printing log information
        """
        super().__init__(session=session, api_url=api_url, data=data, site=site, workers=workers, logger=logger)

        for namespace in self.data["namespaces"]:
            for lb_type in c.F5XC_LOAD_BALANCER_TYPES:
                self.urls.append(self.build_url(c.URI_F5XC_LOAD_BALANCER.format(namespace=namespace, lb_type=lb_type)))

        self.logger.debug("LB_URLS: %s", self.urls)

    def run(self) -> dict:
        """
        Add load balancer to site if load balancer refers to a site. Obtains specific load balancer by name.
        :return: structure with load balancer information being added
        """

        lbs = list()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info("Prepare load balancer query...")
            future_to_ds = {executor.submit(self.get, url=url): url for url in self.urls}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]

                try:
                    data = future.result()
                except Exception as exc:
                    self.logger.info('%r generated an exception: %s' % (_data, exc))
                else:
                    lbs.append({future_to_ds[future]: data.json()["items"]}) if data and data.json()["items"] else None

        def process():
            try:
                lb_name = r["metadata"]["name"]
                site_name = site_info[site_type][site_type]['name']
                namespace = r["metadata"]["namespace"]
                if site_name not in self.data[site_type].keys():
                    self.data[site_type][site_name] = dict()
                if 'namespaces' not in self.data[site_type][site_name].keys():
                    self.data[site_type][site_name]['namespaces'] = dict()
                if namespace not in self.data[site_type][site_name]['namespaces'].keys():
                    self.data[site_type][site_name]['namespaces'][namespace] = dict()
                if "loadbalancer" not in self.data[site_type][site_name]['namespaces'][namespace].keys():
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"] = dict()
                if QUERY_STRING_LB_TCP in future_to_ds[future]:
                    if "tcp" not in self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"].keys():
                        self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["tcp"] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["tcp"][lb_name] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["tcp"][lb_name]['spec'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["tcp"][lb_name]['metadata'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["tcp"][lb_name]['system_metadata'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["tcp"][lb_name]['spec'] = r['spec']
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["tcp"][lb_name]['metadata'] = r['metadata']
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["tcp"][lb_name]['system_metadata'] = r['system_metadata']
                if QUERY_STRING_LB_UDP in future_to_ds[future]:
                    if "udp" not in self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"].keys():
                        self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["udp"] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["udp"][lb_name] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["udp"][lb_name]['spec'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["udp"][lb_name]['metadata'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["udp"][lb_name]['system_metadata'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["udp"][lb_name]['spec'] = r['spec']
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["udp"][lb_name]['metadata'] = r['metadata']
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["udp"][lb_name]['system_metadata'] = r['system_metadata']
                if QUERY_STRING_LB_HTTP in future_to_ds[future]:
                    if "http" not in self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"].keys():
                        self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["http"] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["http"][lb_name] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["http"][lb_name]['spec'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["http"][lb_name]['metadata'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]["loadbalancer"]["http"][lb_name]['system_metadata'] = dict()
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["http"][lb_name]['spec'] = r['spec']
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["http"][lb_name]['metadata'] = r['metadata']
                    self.data[site_type][site_name]['namespaces'][namespace]['loadbalancer']["http"][lb_name]['system_metadata'] = r['system_metadata']
                self.logger.info(f"process loadbalancer add data: [namespace: {namespace} loadbalancer: {lb_name} site_type: {site_type} site_name: {site_name}]")
            except Exception as e:
                self.logger.info("site_type:", site_type)
                self.logger.info("namespace:", r["metadata"]["namespace"])
                self.logger.info("system_metadata:", r['system_metadata'])
                self.logger.info("Exception:", e)

        urls = list()

        for item in lbs:
            for url, lbs in item.items():
                for lb in lbs:
                    _url = "{}/{}".format(url, lb['name'])
                    urls.append(_url)

        self.logger.debug(f"process loadbalancer url: {urls}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}

            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]
                self.must_break = False

                try:
                    self.logger.info(f"process loadbalancer get item: {future_to_ds[future]} ...")
                    result = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % ("process loadbalancer", _data, exc))
                else:
                    self.logger.info(f"process loadbalancer got item: {future_to_ds[future]} ...")

                    if result:
                        r = result.json()
                        self.logger.debug(json.dumps(r, indent=2))

                        if 'advertise_custom' in r['spec'] and 'advertise_where' in r['spec']['advertise_custom']:
                            for site_info in r['spec']['advertise_custom']['advertise_where']:
                                if self.must_break:
                                    break
                                else:
                                    for site_type in site_info.keys():
                                        if site_type in c.F5XC_SITE_TYPES:
                                            # Referenced site must exist
                                            if site_info[site_type][site_type]['name'] in self.data[site_type]:
                                                # Only processing sites which are not in failed state
                                                if site_info[site_type][site_type]['name'] not in self.data["failed"]:
                                                    if self.site:
                                                        if self.site == site_info[site_type][site_type]['name']:
                                                            self.must_break = True
                                                            process()
                                                            break
                                                    else:
                                                        process()

        return self.data
