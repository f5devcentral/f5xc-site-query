import itertools
import os
from abc import ABC
from logging import Logger
from typing import Any

import lib.const as c

PLACE_HOLDER = "N/A"


def join_dict_items(data_dict: dict, separator="\n"):
    """
    Joins all key-value pairs in a dictionary into a single string,
    separated by a specified separator (default is a newline).
    """

    formatted_items = separator.join(f"{key}: {value}" for key, value in data_dict.items())

    return formatted_items


def format_list_with_newlines(value: Any) -> Any:
    """
    Converts a Python list into a string, displaying a maximum of
    two list elements per line, regardless of total length.
    """
    if isinstance(value, list):
        formatted_lines = []

        # Iterate over the list in steps of 2 (i.e., i, i+2, i+4, ...)
        for i in range(0, len(value), 2):
            # Take the current element (value[i])
            line = str(value[i])

            # Check if there is a next element (value[i+1])
            if i + 1 < len(value):
                # If yes, append the next element to the current line
                line += ', ' + str(value[i + 1])

            formatted_lines.append(line)

        # If there's only one line, return the string representation without explicit newlines
        if len(formatted_lines) <= 1:
            return str(value)

        # Join all lines with a newline character.
        # Prepend a newline for better visual alignment in the table cell.
        return '[\'' + ',\n'.join(formatted_lines) + '\']'

    # Return the value unchanged if it's not a list
    return value


class Base(ABC):
    def __init__(self, logger: Logger = None, site: str = None):
        """

        Parameters
        ----------
        :param logger: logger instance
        :param site: site name
        """

        self._logger = logger
        self._site = site
        self._data_common = list()
        self._data_nodes = list()
        self._data_interfaces = list()
        self._data_services = list()
        self._data_services_details = list()
        self._data_service_counter = dict()
        self._data = dict()

    @property
    def logger(self):
        return self._logger

    @property
    def data(self):
        self._data = {
            "common": self.data_common, "nodes": self.data_nodes, "interfaces": self.data_interfaces,
            "services": self.data_services, "services_details": self.data_services_details
        }

        return self._data

    @property
    def data_service_counter(self):
        return self._data_service_counter

    @property
    def data_common(self):
        return self._data_common

    @property
    def data_nodes(self):
        return self._data_nodes

    @property
    def data_interfaces(self):
        return self._data_interfaces

    @property
    def data_services(self):
        return self._data_services

    @property
    def data_services_details(self):
        return self._data_services_details

    @property
    def site(self):
        return self._site

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return f"class: {self.__class__.__name__}"

    def compare(self, source_name: str = None, source_file: str = None, target_name: str = None, target_file: str = None, source_data: dict = None,
                target_data: dict = None) -> dict | None:
        """

        Parameters
        ----------
        source_name
        source_file
        target_name
        target_file
        source_data
        target_data

        Returns
        -------

        """

        self.logger.info(
            f"{self.compare.__name__} started with data from previous run: <{os.path.basename(source_file)}> and data from latest run <{os.path.basename(target_file)}>")
        self.logger.info(f"Compare old site: {source_name} --> {source_file}")
        self.logger.info(f"Compare new site: {target_name} --> {target_file}")

        self.logger.debug(f"DATA_OLD: {source_data}")
        self.logger.debug(f"DATA_NEW: {target_data}")

        if source_data and target_data:
            if source_name in source_data["failed"]:
                self.logger.info(f"Comparing source site <{source_name}> failed. Error site <{source_name}> is in <{source_data["failed"][source_name]}> state")
                return None

            if target_name in target_data["failed"]:
                self.logger.info(f"Comparing target site <{target_name}> failed. Error site <{target_name}> is in <{target_data["failed"][target_name]}> state")
                return None

            if not target_name in target_data[c.SITES_KEY]:
                self.logger.info(f"Comparing target site <{target_name}> not found in file {target_file}.")
                return None

            if not source_name in source_data[c.SITES_KEY]:
                self.logger.info(f"Comparing source site <{source_name}> not found in file {source_file}.")
                return None

            # Only support comparison if site type is of same kind or if source site is secure mesh v1 and destination site is secure mesh v2
            legacy_to_smv2 = source_data[c.SITES_KEY][source_name]['kind'] in [c.F5XC_SITE_TYPE_AWS_VPC, c.F5XC_SITE_TYPE_AWS_TGW, c.F5XC_SITE_TYPE_GCP_VPC,
                                                                               c.F5XC_SITE_TYPE_AZURE_VNET] and target_data[c.SITES_KEY][target_name][
                                 'kind'] == c.F5XC_SITE_TYPE_SMS_V2
            smv1_to_smv2 = source_data[c.SITES_KEY][source_name]['kind'] == c.F5XC_SITE_TYPE_SMS_V1 and target_data[c.SITES_KEY][target_name]['kind'] == c.F5XC_SITE_TYPE_SMS_V2

            if legacy_to_smv2 or smv1_to_smv2:
                source = source_data[c.SITES_KEY][source_name]
                target = target_data[c.SITES_KEY][target_name]
                self._compare_infrastructure(source=source, target=target)
                self._compare_interfaces(source_name=source_name, source_data=source_data, target_name=target_name, target_data=target_data)
                self._compare_services(source=source, target=target)
                self._compare_services_details(source=source, target=target)
                self._compare_services_counter(source=source, target=target)

                return self.data

        return None

    def _compare_infrastructure(self, source: dict = None, target: dict = None) -> list | None:
        """
        Populate compare infrastructure table data

        :param source: source site data to compare with
        :param target: target site data to compare with
        """

        table_data_common = [
            ["Kind", source["kind"], target["kind"]],
            ["Provider Type", source["metadata"]["labels"]["ves.io/provider"] if "ves.io/provider" in target["metadata"]["labels"] else "Unknown",
             target["metadata"]["labels"]["ves.io/provider"] if "ves.io/provider" in target["metadata"]["labels"] else "Unknown"],
            ["Main Node Count", source["main_node_count"], target["main_node_count"]],
            ["Worker Node Count", source["worker_node_count"] if "worker_node_count" in source else 0,
             target["worker_node_count"] if "worker_node_count" in target else 0],
        ]

        if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
            table_data_common.extend([["Labels", join_dict_items(source["sms"]["metadata"]["labels"]), join_dict_items(target["sms"]["metadata"]["labels"])]])
        else:
            table_data_common.extend([["Labels", join_dict_items(source["legacy"]["metadata"]["labels"]), join_dict_items(target["sms"]["metadata"]["labels"])]])

        self.data["common"] = table_data_common

        #######################################
        # Node0 hardware / software           #
        #######################################
        table_data_nodes = [
            ["Node0 Hostname", source["nodes"]["node0"]["hostname"], target["nodes"]["node0"]["hostname"]],
            ["Node0 CPU Count", source["nodes"]["node0"]["hw_info"]["cpu"]["cpus"] if "hw_info" in source["nodes"]["node0"] else 0,
             target["nodes"]["node0"]["hw_info"]["cpu"]["cpus"] if "hw_info" in target["nodes"]["node0"] else "None"],
            ["Node0 CPU Model", source["nodes"]["node0"]["hw_info"]["cpu"]["model"] if "hw_info" in source["nodes"]["node0"] else 0,
             target["nodes"]["node0"]["hw_info"]["cpu"]["model"] if "hw_info" in target["nodes"]["node0"] else "None"],
            ["Node0 Memory Size (GB)", round(source["nodes"]["node0"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in source["nodes"]["node0"] else 0,
             round(target["nodes"]["node0"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in target["nodes"]["node0"] else 0],
            ["Node0 Interface Count", len(source["nodes"]["node0"]["interfaces"]) if "interfaces" in source["nodes"]["node0"] else 0,
             len(target["nodes"]["node0"]["interfaces"]) if "interfaces" in target["nodes"]["node0"] else 0],
            ["Node0 OS Name", source["nodes"]["node0"]["hw_info"]["os"]["name"] if "hw_info" in source["nodes"]["node0"] else "None",
             target["nodes"]["node0"]["hw_info"]["os"]["name"] if "hw_info" in target["nodes"]["node0"] else "None"],
            ["Node0 OS Version", source["nodes"]["node0"]["hw_info"]["os"]["version"] if "hw_info" in source["nodes"]["node0"] else "None",
             target["nodes"]["node0"]["hw_info"]["os"]["version"] if "hw_info" in target["nodes"]["node0"] else "None"],
        ]

        if "hw_info" in source["nodes"]["node0"] and "hw_info" in target["nodes"]["node0"]:
            for storage_source, storage_target in zip(source["nodes"]["node0"]["hw_info"]["storage"], target["nodes"]["node0"]["hw_info"]["storage"]):
                source_node0_storage_size = storage_source["size_gb"]
                target_node0_storage_size = storage_target["size_gb"]
                table_data_nodes.append([f"Node0 Storage {storage_source["name"]} Size (GB)", source_node0_storage_size, target_node0_storage_size])

        #######################################
        # Node1 hardware / software           #
        #######################################
        if source["main_node_count"] > 1 and target["main_node_count"] > 1:
            table_data_nodes.extend(
                [
                    ["Node1 Hostname", source["nodes"]["node1"]["hostname"], target["nodes"]["node1"]["hostname"]],
                    ["Node1 CPU Count", source["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in source["nodes"]["node1"] else 0,
                     target["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in source["nodes"]["node1"] else 0],
                    ["Node1 CPU Model", source["nodes"]["node1"]["hw_info"]["cpu"]["model"] if "hw_info" in source["nodes"]["node1"] else 0,
                     target["nodes"]["node1"]["hw_info"]["cpu"]["model"] if "hw_info" in target["nodes"]["node1"] else "None"],
                    ["Node1 Memory Size (GB)",
                     round(source["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in source["nodes"]["node1"] else 0,
                     round(target["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in target["nodes"]["node1"] else 0],
                    ["Node1 Interface Count", len(source["nodes"]["node1"]["interfaces"]) if "interfaces" in source["nodes"]["node1"] else 0,
                     len(target["nodes"]["node1"]["interfaces"]) if "interfaces" in target["nodes"]["node1"] else 0],
                    ["Node1 OS Name", source["nodes"]["node1"]["hw_info"]["os"]["name"] if "hw_info" in source["nodes"]["node1"] else "None",
                     target["nodes"]["node0"]["hw_info"]["os"]["name"] if "hw_info" in target["nodes"]["node0"] else "None"],
                    ["Node1 OS Version", source["nodes"]["node1"]["hw_info"]["os"]["version"] if "hw_info" in source["nodes"]["node1"] else "None",
                     target["nodes"]["node1"]["hw_info"]["os"]["version"] if "hw_info" in target["nodes"]["node1"] else "None"],
                ]
            )

            if "hw_info" in source["nodes"]["node1"] and "hw_info" in target["nodes"]["node1"]:
                for storage_source, storage_target in zip(source["nodes"]["node1"]["hw_info"]["storage"], target["nodes"]["node1"]["hw_info"]["storage"]):
                    source_node1_storage_size = storage_source["size_gb"]
                    target_node1_storage_size = storage_target["size_gb"]
                    table_data_nodes.append([f"Node1 Storage {storage_source["name"]} Size (GB)", source_node1_storage_size, target_node1_storage_size])

        elif "node1" in source["nodes"] and "node1" not in target["nodes"]:
            table_data_nodes.extend(
                [
                    ["Node1 Hostname", source["nodes"]["node1"]["hostname"], PLACE_HOLDER],
                    ["Node1 CPU Count", source["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in source["nodes"]["node1"] else 0, PLACE_HOLDER],
                    ["Node1 CPU Model", source["nodes"]["node1"]["hw_info"]["cpu"]["model"] if "hw_info" in source["nodes"]["node1"] else 0, PLACE_HOLDER],
                    ["Node1 Memory Size (GB)", round(source["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in source["nodes"]["node1"] else 0,
                     PLACE_HOLDER],
                    ["Node1 Interface Count", len(source["nodes"]["node1"]["interfaces"]) if "interfaces" in source["nodes"]["node1"] else 0, PLACE_HOLDER],
                    ["Node1 OS Name", source["nodes"]["node1"]["hw_info"]["os"]["name"] if "hw_info" in source["nodes"]["node1"] else "None", PLACE_HOLDER],
                    ["Node1 OS Version", source["nodes"]["node1"]["hw_info"]["os"]["version"] if "hw_info" in source["nodes"]["node1"] else "None", PLACE_HOLDER],
                ])

            if "hw_info" in source["nodes"]["node1"]:
                for storage_source in source["nodes"]["node1"]["hw_info"]["storage"]:
                    source_node1_storage_size = storage_source["size_gb"]
                    table_data_nodes.append([f"Node1 Storage {storage_source["name"]} Size (GB)", source_node1_storage_size, PLACE_HOLDER])
        elif "node1" not in source["nodes"] and "node1" in target["nodes"]:
            table_data_nodes.extend(
                [
                    ["Node1 Hostname", PLACE_HOLDER, target["nodes"]["node1"]["hostname"]],
                    ["Node1 CPU Count", PLACE_HOLDER, target["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in target["nodes"]["node1"] else 0],
                    ["Node1 CPU Model", PLACE_HOLDER, target["nodes"]["node1"]["hw_info"]["cpu"]["model"] if "hw_info" in target["nodes"]["node1"] else 0, ],
                    ["Node1 Memory Size (GB)", PLACE_HOLDER,
                     round(target["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in target["nodes"]["node1"] else 0],
                    ["Node1 Interface Count", PLACE_HOLDER, len(target["nodes"]["node1"]["interfaces"]) if "interfaces" in target["nodes"]["node1"] else 0],
                    ["Node1 OS Name", PLACE_HOLDER, target["nodes"]["node1"]["hw_info"]["os"]["name"] if "hw_info" in target["nodes"]["node1"] else "None"],
                    ["Node1 OS Version", PLACE_HOLDER, target["nodes"]["node1"]["hw_info"]["os"]["version"] if "hw_info" in target["nodes"]["node1"] else "None"],
                ])

            if "hw_info" in target["nodes"]["node1"]:
                for storage_target in target["nodes"]["node1"]["hw_info"]["storage"]:
                    target_node1_storage_size = storage_target["size_gb"]
                    table_data_nodes.append([f"Node1 Storage {storage_target["name"]} Size (GB)", PLACE_HOLDER, target_node1_storage_size])

        #######################################
        # Node2 hardware / software           #
        #######################################
        if source["main_node_count"] > 1 and target["main_node_count"] > 1:
            table_data_nodes.extend(
                [
                    ["Node2 Hostname", source["nodes"]["node2"]["hostname"], target["nodes"]["node2"]["hostname"]],
                    ["Node2 CPU Count", source["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in source["nodes"]["node2"] else 0,
                     target["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in source["nodes"]["node2"] else 0],
                    ["Node2 CPU Model", source["nodes"]["node2"]["hw_info"]["cpu"]["model"] if "hw_info" in source["nodes"]["node2"] else 0,
                     target["nodes"]["node2"]["hw_info"]["cpu"]["model"] if "hw_info" in target["nodes"]["node2"] else "None"],
                    ["Node2 Memory Size (GB)",
                     round(source["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in source["nodes"]["node2"] else 0,
                     round(target["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in target["nodes"]["node2"] else 0],
                    ["Node2 Interface Count", len(source["nodes"]["node2"]["interfaces"]) if "interfaces" in source["nodes"]["node2"] else 0,
                     len(target["nodes"]["node2"]["interfaces"]) if "interfaces" in target["nodes"]["node2"] else 0],
                    ["Node2 OS Name", source["nodes"]["node2"]["hw_info"]["os"]["name"] if "hw_info" in source["nodes"]["node2"] else "None",
                     target["nodes"]["node0"]["hw_info"]["os"]["name"] if "hw_info" in target["nodes"]["node0"] else "None"],
                    ["Node2 OS Version", source["nodes"]["node2"]["hw_info"]["os"]["version"] if "hw_info" in source["nodes"]["node2"] else "None",
                     target["nodes"]["node2"]["hw_info"]["os"]["version"] if "hw_info" in target["nodes"]["node2"] else "None"],
                ]
            )

            if "hw_info" in source["nodes"]["node2"] and "hw_info" in target["nodes"]["node2"]:
                for storage_source, storage_target in zip(source["nodes"]["node2"]["hw_info"]["storage"], target["nodes"]["node2"]["hw_info"]["storage"]):
                    source_node2_storage_size = storage_source["size_gb"]
                    target_node2_storage_size = storage_target["size_gb"]
                    table_data_nodes.append([f"node2 Storage {storage_source["name"]} Size (GB)", source_node2_storage_size, target_node2_storage_size])

        elif "node2" in source["nodes"] and "node2" not in target["nodes"]:
            table_data_nodes.extend(
                [
                    ["node2 Hostname", source["nodes"]["node2"]["hostname"], PLACE_HOLDER],
                    ["node2 CPU Count", source["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in source["nodes"]["node2"] else 0, PLACE_HOLDER],
                    ["node2 CPU Model", source["nodes"]["node2"]["hw_info"]["cpu"]["model"] if "hw_info" in source["nodes"]["node2"] else 0, PLACE_HOLDER],
                    ["node2 Memory Size (GB)",
                     round(source["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in source["nodes"]["node2"] else 0,
                     PLACE_HOLDER],
                    ["node2 Interface Count", len(source["nodes"]["node2"]["interfaces"]) if "interfaces" in source["nodes"]["node2"] else 0, PLACE_HOLDER],
                    ["node2 OS Name", source["nodes"]["node2"]["hw_info"]["os"]["name"] if "hw_info" in source["nodes"]["node2"] else "None", PLACE_HOLDER],
                    ["node2 OS Version", source["nodes"]["node2"]["hw_info"]["os"]["version"] if "hw_info" in source["nodes"]["node2"] else "None",
                     PLACE_HOLDER],
                ])

            if "hw_info" in source["nodes"]["node2"]:
                for storage_source in source["nodes"]["node2"]["hw_info"]["storage"]:
                    source_node2_storage_size = storage_source["size_gb"]
                    table_data_nodes.append([f"node2 Storage {storage_source["name"]} Size (GB)", source_node2_storage_size, PLACE_HOLDER])
        elif "node2" not in source["nodes"] and "node2" in target["nodes"]:
            table_data_nodes.extend(
                [
                    ["node2 Hostname", PLACE_HOLDER, target["nodes"]["node2"]["hostname"]],
                    ["node2 CPU Count", PLACE_HOLDER, target["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in target["nodes"]["node2"] else 0],
                    ["node2 CPU Model", PLACE_HOLDER, target["nodes"]["node2"]["hw_info"]["cpu"]["model"] if "hw_info" in target["nodes"]["node2"] else 0, ],
                    ["node2 Memory Size (GB)", PLACE_HOLDER,
                     round(target["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] / 1024) if "hw_info" in target["nodes"]["node2"] else 0],
                    ["node2 Interface Count", PLACE_HOLDER, len(target["nodes"]["node2"]["interfaces"]) if "interfaces" in target["nodes"]["node2"] else 0],
                    ["node2 OS Name", PLACE_HOLDER, target["nodes"]["node2"]["hw_info"]["os"]["name"] if "hw_info" in target["nodes"]["node2"] else "None"],
                    ["node2 OS Version", PLACE_HOLDER,
                     target["nodes"]["node2"]["hw_info"]["os"]["version"] if "hw_info" in target["nodes"]["node2"] else "None"],
                ])

            if "hw_info" in target["nodes"]["node2"]:
                for storage_target in target["nodes"]["node2"]["hw_info"]["storage"]:
                    target_node2_storage_size = storage_target["size_gb"]
                    table_data_nodes.append([f"node2 Storage {storage_target["name"]} Size (GB)", PLACE_HOLDER, target_node2_storage_size])

        self._data_nodes = table_data_nodes

        return self.data_nodes

    def _compare_interfaces(self, source_name: str = None, source_data: dict[str, Any] = None, target_name: str = None, target_data: dict[str, Any] = None) -> list[dict[
        str, Any]] | None:
        pass

    def _compare_services(self, source: dict = None, target: dict = None) -> list | None:
        """
               Populate compare services detail table data

               :param source: source site data to compare with
               :param target: target site data to compare with
               """

        source_ns = list()
        target_ns = list()
        source_lbs = list()
        target_lbs = list()
        source_ops = list()
        target_ops = list()
        source_proxies = list()
        target_proxies = list()

        if "namespaces" in source:
            for namespace in source["namespaces"]:
                source_ns.append(namespace)
            for source_item in source["namespaces"].values():
                if "loadbalancer" in source_item.keys():
                    for source_lb_type in source_item["loadbalancer"].keys():
                        source_lbs.extend(list(source_item["loadbalancer"][source_lb_type].keys()))

                if "proxys" in source_item.keys():
                    for source_proxy_type in source_item["proxys"].keys():
                        source_proxies.append(source_item["proxys"][source_proxy_type]["metadata"]["name"])

            for source_item in source["namespaces"].values():
                if "origin_pools" in source_item.keys():
                    source_ops.extend(list(source_item["origin_pools"].keys()))

        if "namespaces" in target:
            for namespace in target["namespaces"]:
                target_ns.append(namespace)
            for target_item in target["namespaces"].values():
                if "loadbalancer" in target_item.keys():
                    for target_lb_type in target_item["loadbalancer"].keys():
                        target_lbs.extend(list(target_item["loadbalancer"][target_lb_type].keys()))

                if "proxys" in target_item.keys():
                    for target_proxy_type in target_item["proxys"].keys():
                        target_proxies.append(target_item["proxys"][target_proxy_type]["metadata"]["name"])

            for ns, target_item in target["namespaces"].items():
                if "origin_pools" in target_item.keys():
                    target_ops.extend(list(target_item["origin_pools"].keys()))

        table_data_services = [
            ['Namespaces', len(source_ns), len(target_ns)],
            ['LoadBalancer', len(source_lbs), len(target_lbs)],
            ['OriginPools', len(source_ops), len(target_ops)],
            ['EFP', len(list(source["efp"].keys())) if "efp" in source else 0, len(list(target["efp"].keys())) if "efp" in target else 0],
            ['FPP', len(list(source["fpp"].keys())) if "fpp" in source else 0, len(list(target["fpp"].keys())) if "fpp" in target else 0],
            ['SMG', len(list(source["smg"].keys())) if len(source["smg"]) > 0 else 0, len(list(target["smg"].keys())) if len(target["smg"]) > 0 else 0],
            ['DCCG', len(list(source["dc_cluster_group"].keys())) if "dc_cluster_group" in source else 0, len(list(target["dc_cluster_group"].keys())) if "dc_cluster_group" in target else 0],
            ['Proxies', len(source_proxies) if len(source_proxies) > 0 else 0, len(target_proxies) if len(target_proxies) > 0 else 0],
            ['Segments', len(source["segments"].keys()) if "segments" in source else 0, len(target["segments"].keys()) if "segments" in target else 0],
            ['BGP Policies', len(list(source["bgp"].keys())) if "bgp" in source else 0, len(list(target["bgp"].keys())) if "bgp" in target else 0],
            ['Virtual Sites', len(source["vsites"]), len(target["vsites"])],
        ]

        self._data_services = table_data_services

        return self.data_services

    def _compare_services_counter(self, source: dict = None, target: dict = None) -> dict | None:
        """
        Dict representation of services and according counter
        Returns
        -------

        """

        source_ns = list()
        target_ns = list()
        source_lbs = list()
        target_lbs = list()
        source_proxies = list()
        target_proxies = list()
        ops = dict()

        if "namespaces" in source and "namespaces" in target:
            for namespace in source["namespaces"]:
                source_ns.append(namespace)
            for source_item in source["namespaces"].values():
                if "loadbalancer" in source_item.keys():
                    for source_lb_type in source_item["loadbalancer"].keys():
                        source_lbs.extend(list(source_item["loadbalancer"][source_lb_type].keys()))

                if "proxys" in source_item.keys():
                    for source_proxy_type in source_item["proxys"].keys():
                        source_proxies.append(source_item["proxys"][source_proxy_type]["metadata"]["name"])

            for ns, source_item in source["namespaces"].items():
                if "origin_pools" in source_item.keys():
                    ops[f"OriginPools[{ns}]"] = [len(list(source_item["origin_pools"].keys()))]

            for namespace in target["namespaces"]:
                target_ns.append(namespace)

            for target_item in target["namespaces"].values():
                if "loadbalancer" in target_item.keys():
                    for target_lb_type in target_item["loadbalancer"].keys():
                        target_lbs.extend(list(target_item["loadbalancer"][target_lb_type].keys()))

                if "proxys" in target_item.keys():
                    for target_proxy_type in target_item["proxys"].keys():
                        target_proxies.append(target_item["proxys"][target_proxy_type]["metadata"]["name"])

            for ns, target_item in source["namespaces"].items():
                if "origin_pools" in target_item.keys():
                    ops[f"OriginPools[{ns}]"] = [len(list(target_item["origin_pools"].keys()))]
        elif "namespace" in source and "namespaces" not in target:
            for namespace in source["namespaces"]:
                source_ns.append(namespace)
            for source_item in source["namespaces"].values():
                if "loadbalancer" in source_item.keys():
                    for source_lb_type in source_item["loadbalancer"].keys():
                        source_lbs.extend(list(source_item["loadbalancer"][source_lb_type].keys()))

                if "proxys" in source_item.keys():
                    for source_proxy_type in source_item["proxys"].keys():
                        source_proxies.append(source_item["proxys"][source_proxy_type]["metadata"]["name"])

            for ns, source_item in source["namespaces"].items():
                if "origin_pools" in source_item.keys():
                    ops[f"OriginPools[{ns}]"] = [len(list(source_item["origin_pools"].keys())), 0]

            for namespace in target["namespaces"]:
                target_ns.append(namespace)
        elif "namespace" not in source and "namespaces" in target:
            for namespace in target["namespaces"]:
                target_ns.append(namespace)
            for target_item in target["namespaces"].values():
                if "loadbalancer" in target_item.keys():
                    for target_lb_type in target_item["loadbalancer"].keys():
                        target_lbs.extend(list(target_item["loadbalancer"][target_lb_type].keys()))

                if "proxys" in target_item.keys():
                    for target_proxy_type in target_item["proxys"].keys():
                        target_proxies.append(target_item["proxys"][target_proxy_type]["metadata"]["name"])

            for ns, target_item in target["namespaces"].items():
                if f"OriginPools[{ns}]" not in ops:
                    ops[f"OriginPools[{ns}]"] = list()

                if "origin_pools" in target_item.keys():
                    ops[f"OriginPools[{ns}]"] = [0, len(list(target_item["origin_pools"].keys()))]

        table_data_services = {
            "Namespaces": [len(source_ns), len(target_ns)],
            "LoadBalancer": [len(source_lbs), len(target_lbs)],
        }
        table_data_services.update(ops)
        table_data_services.update(
            {
                "EFP": [len(list(source["efp"].keys())) if "efp" in source else 0, len(list(target["efp"].keys())) if "efp" in target else 0],
                "FPP": [len(list(source["fpp"].keys())) if "fpp" in source else 0, len(list(target["fpp"].keys())) if "fpp" in target else 0],
                "SMG": [len(list(source["smg"].keys())) if len(source["smg"]) > 0 else 0, len(list(target["smg"].keys())) if len(target["smg"]) > 0 else 0],
                "DCCG": [len(list(source["dc_cluster_group"].keys())) if "dc_cluster_group" in source else 0,
                         len(list(target["dc_cluster_group"].keys())) if "dc_cluster_group" in target else 0],
                "Proxies": [len(source_proxies) if len(source_proxies) > 0 else 0, len(target_proxies) if len(target_proxies) > 0 else 0],
                "Segments": [len(source["segments"].keys()) if "segments" in source else 0, len(target["segments"].keys()) if "segments" in target else 0],
                "BGP Policies": [len(list(source["bgp"].keys())) if "bgp" in source else 0, len(list(target["bgp"].keys())) if "bgp" in target else 0],
                "Virtual Sites": [len(source["vsites"]), len(target["vsites"])],
            }
        )

        self._data_service_counter = table_data_services

        return self.data_service_counter

    def _compare_services_details(self, source: dict = None, target: dict = None) -> list | None:
        """
        Populate compare services detail table data

        :param source: source site data to compare with
        :param target: target site data to compare with
        """

        source_ns = list()
        target_ns = list()
        source_lbs = list()
        source_ops = list()
        target_lbs = list()
        target_ops = list()
        source_proxies = list()
        target_proxies = list()

        if "namespaces" in source and "namespaces" in target:
            for namespace in source["namespaces"]:
                source_ns.append(namespace)
            for source_item in source["namespaces"].values():
                if "loadbalancer" in source_item.keys():
                    for source_lb_type in source_item["loadbalancer"].keys():
                        source_lbs.extend(list(source_item["loadbalancer"][source_lb_type].keys()))

                if "proxys" in source_item.keys():
                    for source_proxy_type in source_item["proxys"].keys():
                        source_proxies.append(source_item["proxys"][source_proxy_type]["metadata"]["name"])

            for ns, source_item in source["namespaces"].items():
                if "origin_pools" in source_item.keys():
                    a = f"OriginPools[{ns}]", list(source_item["origin_pools"].keys())
                    source_ops.append(a)

            for namespace in target["namespaces"]:
                target_ns.append(namespace)
            for target_item in target["namespaces"].values():
                if "loadbalancer" in target_item.keys():
                    for target_lb_type in target_item["loadbalancer"].keys():
                        target_lbs.extend(list(target_item["loadbalancer"][target_lb_type].keys()))

                if "proxys" in target_item.keys():
                    for target_proxy_type in target_item["proxys"].keys():
                        target_proxies.append(target_item["proxys"][target_proxy_type]["metadata"]["name"])

            for ns, target_item in target["namespaces"].items():
                if "origin_pools" in target_item.keys():
                    a = [list(target_item["origin_pools"].keys())]
                    target_ops.append(a)

        elif "namespaces" in source and "namespaces" not in target:
            # Only source namespace exists

            for namespace in source["namespaces"]:
                source_ns.append(namespace)
            for source_item in source["namespaces"].values():
                if "loadbalancer" in source_item.keys():
                    for source_lb_type in source_item["loadbalancer"].keys():
                        source_lbs.extend(list(source_item["loadbalancer"][source_lb_type].keys()))

                if "proxys" in source_item.keys():
                    for source_proxy_type in source_item["proxys"].keys():
                        source_proxies.append(source_item["proxys"][source_proxy_type]["metadata"]["name"])

            for ns, source_item in source["namespaces"].items():
                if "origin_pools" in source_item.keys():
                    a = [f"OriginPools[{ns}]", list(source_item["origin_pools"].keys()), PLACE_HOLDER]
                    source_ops.append(a)

        elif "namespaces" not in source and "namespaces" in target:
            # Only target namespace exist
            for namespace in target["namespaces"]:
                target_ns.append(namespace)

            for target_item in target["namespaces"].values():
                if "loadbalancer" in target_item.keys():
                    for target_lb_type in target_item["loadbalancer"].keys():
                        target_lbs.extend(list(target_item["loadbalancer"][target_lb_type].keys()))

                if "proxys" in target_item.keys():
                    for target_proxy_type in target_item["proxys"].keys():
                        target_proxies.append(target_item["proxys"][target_proxy_type]["metadata"]["name"])

            for ns, target_item in target["namespaces"].items():
                if "origin_pools" in target_item.keys():
                    target_ops.append([f"OriginPools[{ns}]", PLACE_HOLDER, format_list_with_newlines(list(target_item["origin_pools"].keys()))])

        table_data_services = [
            ['Namespaces', format_list_with_newlines(source_ns) if len(source_ns) > 0 else "None", format_list_with_newlines(target_ns) if len(target_ns) > 0 else "None"],
            ["new_section"],
            ['LoadBalancer', format_list_with_newlines(source_lbs) if len(source_lbs) > 0 else "None", format_list_with_newlines(target_lbs) if len(target_lbs) > 0 else "None"],
            ["new_section"],
        ]

        # Origin Pools
        if len(source_ns) > 0:
            #a = [source_ops if len(source_ops) > 0 else "None", target_ops if len(target_ops) > 0 else "None"],
            table_data_services.extend([source_ops, target_ops])
        else:
            table_data_services.extend(target_ops)

        table_data_services.append(["new_section"])

        table_data_services.extend(
            [
                ['EFP', format_list_with_newlines(list(source["efp"].keys())) if "efp" in source else "None",
                 format_list_with_newlines(list(target["efp"].keys())) if "efp" in target else "None"],
                ["new_section"],
                ['FPP', format_list_with_newlines(list(source["fpp"].keys())) if "fpp" in source else "None",
                 format_list_with_newlines(list(target["fpp"].keys())) if "fpp" in target else "None"],
                ['SMG', format_list_with_newlines(list(source["smg"].keys())) if len(source["smg"]) > 0 else "None",
                 format_list_with_newlines(list(target["smg"].keys())) if len(target["smg"]) > 0 else "None"],
                ["new_section"],
                ['DCCG', format_list_with_newlines(list(source["dc_cluster_group"].keys())) if "dc_cluster_group" in source else "None",
                 format_list_with_newlines(list(target["dc_cluster_group"].keys())) if "dc_cluster_group" in target else "None"],
                ['Proxies', format_list_with_newlines(source_proxies) if len(source_proxies) > 0 else "None",
                 format_list_with_newlines(target_proxies) if len(target_proxies) > 0 else "None"],
                ["new_section"],
                ['Segments', format_list_with_newlines(source["segments"].keys()) if "segments" in source else "None",
                 format_list_with_newlines(target["segments"].keys()) if "segments" in target else "None"],
                ["new_section"],
                ['BGP Policies', format_list_with_newlines(list(source["bgp"].keys())) if "bgp" in source else "None",
                 format_list_with_newlines(list(target["bgp"].keys())) if "bgp" in target else "None"],
                ["new_section"],
                ['Virtual Sites', format_list_with_newlines(source["vsites"]) if len(source["vsites"]) > 0 else "None",
                 format_list_with_newlines(target["vsites"]) if len(target["vsites"]) else "None"],
            ]
        )

        self._data_services_details = table_data_services

        return self.data_services_details
