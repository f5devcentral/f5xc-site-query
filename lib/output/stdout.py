import itertools
from logging import Logger
from typing import Any


import lib.const as c
from lib.output.base import Base, PLACE_HOLDER
from lib.output.base import format_list_with_newlines
from prettytable import PrettyTable, TableStyle

class StdoutTable(Base):
    def __init__(self, logger: Logger, site: str = None):
        super().__init__(logger=logger, site=site)
        self.must_break = None
        self._table = PrettyTable()
        self.table.set_style(TableStyle.SINGLE_BORDER)
        self.table.field_names = ["Item", "Source", "Target"]

        if self.site:
            self.table.padding_width = 1
            self.table.title = self.site

    @property
    def table(self):
        return self._table


    def build_inventory(self, data: dict = None) -> PrettyTable | None:
        """
        Build site inventory

        :return: inventory data

        Parameters
        ----------
        data: dict
        """

        self.logger.info(f"{self.build_inventory.__name__} started...")

        if data:
            table = PrettyTable()
            table.set_style(TableStyle.SINGLE_BORDER)
            table.field_names = ["No", "Type", "Value", "Subtype1", "SubValue1", "Subtype2", "SubValue2"]
            table.title = "Inventory"
            table.padding_width = 1

            def process():
                record_no = 1
                table.add_row(["{}".format(site), "", "", "", "", "", ""])
                for key, value in site_data.items():
                    if isinstance(value, str):
                        table.add_row([record_no, key, value, "", "", "", ""])
                    elif isinstance(value, int):
                        table.add_row([record_no, key, value, "", "", "", ""])
                    elif isinstance(value, dict):
                        if key in c.CSV_EXPORT_KEYS:
                            if key == "spec":
                                table.add_row([record_no, key, "ce_sw_version", value["volterra_software_version"], "", "", ""])
                            elif key == "spoke":
                                if site_data["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                                    # TODO add azure support
                                    pass
                                elif site_data["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                                    table.add_row([record_no, key, len(value["vpc_list"]), "", "", "", ""])
                            elif key == "nodes":
                                for node, attrs in value.items():
                                    if "interfaces" in attrs:
                                        table.add_row([record_no, "node", node, "interfaces", len(attrs["interfaces"]), "", ""])
                                    if "hw_info" in attrs:
                                        for k, v in c.HW_INFO_ITEMS_TO_PROCESS.items():
                                            if k == "storage":
                                                for s in attrs["hw_info"][k]:
                                                    for item in v:
                                                        if s[item] != 0:
                                                            table.add_row([record_no, "node", node, "hw_info", k, s["name"], s[item]])
                                            else:
                                                for item in v:
                                                    table.add_row([record_no, "node", node, "hw_info", k, item, attrs["hw_info"][k][item]])
                            elif key == "namespaces":
                                for namespace, attrs in value.items():
                                    for ns_item, ns_item_value in attrs.items():
                                        if ns_item == "loadbalancer":
                                            for lb, lb_values in ns_item_value.items():
                                                table.add_row([record_no, key, namespace, ns_item, lb, "",
                                                               '\n'.join(list(lb_values.keys())) if len(lb_values.keys()) > 1 else list(lb_values.keys())[0]])
                                        else:
                                            table.add_row([record_no, key, namespace, ns_item,
                                                           '\n'.join(list(ns_item_value.keys())) if len(ns_item_value.keys()) > 1 else list(ns_item_value.keys())[0], "", ""])
                            else:
                                for name in value:
                                    table.add_row([record_no, key, name, "", "", "", ""])
                    elif isinstance(value, list):
                        if len(value) > 0:
                            table.add_row([record_no, key, format_list_with_newlines(value), "", "", "", ""])
                    record_no += 1

                table.add_divider()

            for site, site_data in data[c.SITES_KEY].items():
                if self.must_break:
                    break
                else:
                    if self.site:
                        if self.site == site:
                            self.must_break = True
                            process()
                            break
                    else:
                        process()

            self.logger.info(f"{self.build_inventory.__name__} -> Done")

            return table

        return None

    def build_comparison(self, source_name: str = None, source_file: str = None, target_name: str = None, target_file: str = None, source_data: dict = None, target_data: dict = None) -> PrettyTable | None:
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

        self.logger.info(f"Stdout {self.build_comparison.__name__} started...")
        data = self.compare(source_name=source_name, source_file=source_file, target_name=target_name, target_file=target_file, source_data=source_data, target_data=target_data)

        if data:
            self.table.add_rows(self.data_common)
            self.table.add_divider()
            self.table.add_rows(self.data_nodes)
            self.table.add_divider()
            self.table.add_rows(self.data_interfaces)
            self.table.add_divider()

            for service in self.data_services_details:
                service_name = service[0]
                if service_name == "new_section":
                    self.table.add_divider()
                else:
                    counter_row = [f"{service_name} Counter", self.data_service_counter.get(service_name)[0], self.data_service_counter.get(service_name)[1]]
                    self.table.add_row(counter_row)
                    self.table.add_row(service)


        self.logger.info(f"Stdout {self.build_comparison.__name__}. Done.")
        return self.table

    def _compare_interfaces(self, source_name: str = None, source_data: dict[str, Any] = None, target_name: str = None, target_data: dict[str, Any] = None) -> list[dict[str, Any]] | None:
        #######################################
        # Node0 Interfaces                    #
        #######################################
        if source_data and target_data:
            source = source_data[c.SITES_KEY][source_name]
            target = target_data[c.SITES_KEY][target_name]

            table_data_node_interfaces = list()
            source_node0_interfaces = list()
            target_node0_interfaces = list()

            if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                node_interfaces = list()
                for interface in source["node0"]["interfaces"]:
                    if "dedicated_interface" in interface.keys():
                        node_interfaces.append(interface["dedicated_interface"]["device"])
                    if "ethernet_interface" in interface.keys():
                        node_interfaces.append(interface["dedicated_interface"]["device"])
                source_node0_interfaces.append(["Node0", format_list_with_newlines(node_interfaces)])
            else:
                # Legacy sites
                source_node0_interfaces.append("".join(source["nodes"]["node0"]["interfaces"].keys()))

            if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                target_node0_interfaces = [interface["name"] for interface in target["nodes"]["node0"]["interfaces"]]

            table_data_node_interfaces.append(["Node0", format_list_with_newlines(source_node0_interfaces), target_node0_interfaces])

            #######################################
            # Node1 Interfaces                    #
            #######################################
            source_node1_interfaces = list()
            target_node1_interfaces = list()

            if source["main_node_count"] > 1 and target["main_node_count"] > 1:
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    node_interfaces = list()
                    for interface in source["node0"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                        if "ethernet_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                    source_node1_interfaces.append(["Node1", format_list_with_newlines(node_interfaces)])
                else:
                    # Legacy sites
                    source_node1_interfaces.append("".join(source["nodes"]["node1"]["interfaces"].keys()))

                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node1_interfaces = [interface["name"] for interface in target["nodes"]["node0"]["interfaces"]]

                table_data_node_interfaces.append(["Node0", format_list_with_newlines(source_node1_interfaces), target_node1_interfaces])
            elif source["main_node_count"] > 2 < target["main_node_count"]:
                print("only source no target")
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    node_interfaces = list()
                    for interface in source["node1"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                        if "ethernet_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                    source_node1_interfaces.append(["Node1", format_list_with_newlines(node_interfaces)])
                else:
                    # Legacy sites
                    source_node1_interfaces.append("".join(source["nodes"]["node1"]["interfaces"].keys()))
                table_data_node_interfaces.append(["Node1", source_node1_interfaces, PLACE_HOLDER])
            elif source["main_node_count"] <= 1 < target["main_node_count"]:
                print("no source only target")
                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node1_interfaces = [interface["name"] for interface in target["nodes"]["node1"]["interfaces"]]
                table_data_node_interfaces.append(["Node1", PLACE_HOLDER, target_node1_interfaces])

            #######################################
            # Node2 Interfaces                    #
            #######################################
            source_node2_interfaces = list()
            target_node2_interfaces = list()

            if source["main_node_count"] > 1 and target["main_node_count"] > 1:
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    node_interfaces = list()
                    for interface in source["node2"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                        if "ethernet_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                    source_node2_interfaces.append(["Node2", format_list_with_newlines(node_interfaces)])
                else:
                    # Legacy sites
                    source_node2_interfaces.append("".join(source["nodes"]["node2"]["interfaces"].keys()))

                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node2_interfaces = [interface["name"] for interface in target["nodes"]["node0"]["interfaces"]]

                table_data_node_interfaces.append(["Node2", format_list_with_newlines(source_node2_interfaces), target_node2_interfaces])
            elif source["main_node_count"] > 2 < target["main_node_count"]:
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    node_interfaces = list()
                    for interface in source["node2"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                        if "ethernet_interface" in interface.keys():
                            node_interfaces.append(interface["dedicated_interface"]["device"])
                    source_node2_interfaces.append(["Node2", format_list_with_newlines(node_interfaces)])
                else:
                    # Legacy sites
                    source_node2_interfaces.append("".join(source["nodes"]["node2"]["interfaces"].keys()))
                table_data_node_interfaces.append(["Node2", source_node2_interfaces, PLACE_HOLDER])
            elif source["main_node_count"] < 2 < target["main_node_count"]:
                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node2_interfaces = [interface["name"] for interface in target["nodes"]["node2"]["interfaces"]]
                table_data_node_interfaces.append(["Node2", PLACE_HOLDER, target_node2_interfaces])

            self._data_interfaces = table_data_node_interfaces

            return self.data["interfaces"]
        else:
            return None

"""
              compare_paths = [
                  "metadata/name",
                  "kind",
                  "metadata/labels",
                  "main_node_count",
                  "worker_node_count",
                  "nodes",
                  "efp",
                  "fpp",
                  "bgp",
                  "smg",
                  "segments",
                  "dc_cluster_group",
                  "vsites",
                  "namespaces",
                  "namespaces/loadbalancer",
                  "namespaces/proxys",
                  "namespaces/origin_pools",
              ]

              source_table_data = list()
              target_table_data = list()

              def recurse(key_path: list, data, table_data):
                  if len(key_path) > 1:
                      recurse(key_path[1:], data[key_path[0]], table_data)
                  else:
                      if key_path[0] == "namespaces":
                          table_data.extend(["add_section_title_namespaces", "namespaces"])
                          table_data.extend([f"namespaces_count", len(data.get(key_path[0]).keys())])
                          table_data.extend([f"namespaces", format_list_with_newlines([namespace for namespace in data.get(key_path[0]).keys()])])
                      elif key_path[0] == "labels":
                          _labels = data.get(key_path[0])
                          for label_key, label_value in _labels.items():
                              if label_key == "ves.io/provider":
                                  table_data.extend(["provider_type", label_value])
                      elif key_path[0] == "nodes":
                          table_data.extend([f"add_section_title_nodes", f"nodes"])
                          for node_name, node_values in data[key_path[0]].items():
                              if node_name in ["node0", "node1", "node2"]:
                                  table_data.extend([f"{node_name}_hostname", node_values["hostname"]])
                                  table_data.extend([f"{node_name}_cpu_count", node_values["hw_info"]["cpu"]["cpus"]])
                                  table_data.extend([f"{node_name}_cpu_model", node_values["hw_info"]["cpu"]["model"]])
                                  table_data.extend([f"{node_name}_memory_size", f"{round(node_values["hw_info"]["memory"]["size_mb"] / 1024)} GB"])
                                  table_data.extend([f"{node_name}_interface_count", len(node_values["interfaces"])])
                                  table_data.extend([f"{node_name}_os_name", node_values["hw_info"]["os"]["name"]])
                                  table_data.extend([f"{node_name}_os_version", node_values["hw_info"]["os"]["version"]])
                                  for index, storage in enumerate(node_values["hw_info"]["storage"]):
                                      table_data.extend([f"{node_name}_storage_{index}", f"{storage["size_gb"]} GB"])
                          # Interfaces
                          if data["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                              for node_name, node_values in data[key_path[0]].items():
                                  node_interfaces = list()
                                  for interface in node_values["interfaces"]:
                                      interface_details = dict()
                                      # table_data.extend([f"add_section_title_{node_name}_interfaces", "node_interfaces"])
                                      if "dedicated_interface" in interface.keys():
                                          interface_details["is_primary"] = "true" if "is_primary" in interface["dedicated_interface"].keys() else "false"
                                          interface_details["device_name"] = interface["dedicated_interface"]["device"]
                                          interface_details["description"] = interface["description"] if interface["description"] != "" else "None"
                                          interface_details["interface_type"] = "dedicated_interface"
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_is_primary", interface_details["is_primary"]])
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_description", interface_details["description"]])
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_type", interface_details["interface_type"]])
                                          node_interfaces.append(interface_details["device_name"])
                                      if "ethernet_interface" in interface.keys():
                                          interface_details["mtu"] = interface["ethernet_interface"]["mtu"]
                                          interface_details["is_primary"] = True if "is_primary" in interface["ethernet_interface"].keys() else False
                                          interface_details["dhcp_server"] = "true" if "dhcp_server" in interface.keys() else "false"
                                          interface_details["device_name"] = interface["ethernet_interface"]["device"]
                                          interface_details["description"] = interface["description"] if interface["description"] != "" else "None"
                                          if "dhcp_server" in interface["ethernet_interface"].keys():
                                              network_prefixes = list()
                                              for network in interface["ethernet_interface"]["dhcp_server"]["dhcp_networks"]:
                                                  network_prefixes.append(network["network_prefix"])
                                              interface_details["dhcp_networks"] = ",".join(network_prefixes) if network_prefixes else "None"
                                          interface_details["interface_type"] = "ethernet_interface"
                                          interface_details["segment_network"] = interface["ethernet_interface"]["segment_network"]["name"] if "segment_network" in interface[
                                              "ethernet_interface"].keys() else "None"
                                          node_interfaces.append(interface_details["device_name"])

                                      # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_type", interface_details["interface_type"]])
                                      # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_description", interface_details["description"]])
                                      # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_is_primary", interface_details["is_primary"]])
                                      # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_server", interface_details["dhcp_server"]])
                                      # if "dhcp_networks" in interface_details.keys():
                                      #     table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_networks", interface_details["dhcp_networks"]])
                                  table_data.extend([f"{node_name}_interfaces", format_list_with_newlines(node_interfaces)])
                          elif data["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                              for node_name, node_values in data[key_path[0]].items():
                                  node_interfaces = list()
                                  for interface in node_values["interfaces"]:
                                      interface_details = dict()
                                      interface_details["mtu"] = interface["mtu"] if "mtu" in interface else "None"
                                      interface_details["is_primary"] = interface["is_primary"] if "is_primary" in interface else "None"
                                      interface_details["description"] = interface["description"] if interface["description"] != "" else "None"
                                      interface_details["is_management"] = interface["is_management"] if "is_management" in interface else "None"
                                      interface_details["site_local_network"] = "True" if "site_local_network" in interface["network_option"] else "None"
                                      interface_details["site_local_inside_network"] = "True" if "site_local_inside_network" in interface["network_option"] else "None"
                                      interface_details["dhcp_client"] = "True" if "dhcp_client" in interface else "False"
                                      interface_details["dhcp_server"] = "true" if "dhcp_server" in interface.keys() else "false"
                                      interface_details["segment_network"] = interface["network_option"]["segment_network"]["name"] if "segment_network" in interface[
                                          "network_option"].keys() else "None"
                                      if "dhcp_server" in interface.keys():
                                          network_prefixes = list()
                                          for network in interface["dhcp_server"]["dhcp_networks"]:
                                              network_prefixes.append(network["network_prefix"])
                                          interface_details["dhcp_networks"] = ",".join(network_prefixes) if network_prefixes else "None"
                                      if "ethernet_interface" in interface.keys():
                                          interface_details["device_name"] = interface["ethernet_interface"]["device"]
                                          interface_details["interface_type"] = "ethernet_interface"
                                          interface_details["mac"] = interface["ethernet_interface"]["mac"] if "ethernet_interface" in interface[
                                              "ethernet_interface"].keys() else "None"
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_type", interface_details["interface_type"]])
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_description", interface_details["description"]])
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_is_primary", interface_details["is_primary"]])
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_site_local_network", interface_details["site_local_network"]])
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_site_local_inside_network", interface_details["site_local_inside_network"]])
                                          # table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_server", interface_details["dhcp_server"]])
                                          # if "dhcp_networks" in interface_details.keys():
                                          #    table_data.extend([f"{node_name}_interface_{interface_details["device_name"]}_dhcp_networks", interface_details["dhcp_networks"]])
                                      node_interfaces.append(interface["name"])
                                  table_data.extend([f"{node_name}_interfaces", format_list_with_newlines(node_interfaces)])
                          else:
                              # Legacy sites
                              for node_name, node_values in data[key_path[0]].items():
                                  node_interfaces = list()
                                  for interface_name, interface_attrs in node_values["interfaces"].items():
                                      interface_details = dict()
                                      #interface_details["device_name"] = interface_name
                                      #interface_details["ipv4"] = interface_attrs["subnet_param"]["ipv4"] if "subnet_param" in interface_attrs else None
                                      #interface_details["ipv6"] = interface_attrs["subnet_param"]["ipv6"] if "subnet_param" in interface_attrs else None
                                      #interface_details["existing_subnet_id"] = interface_attrs["existing_subnet_id"] if "existing_subnet_id" in interface_attrs else None
                                      #_interface = [f"Node0", f"{interface_details["device_name"]}", join_dict_items(interface_details)]
                                      node_interfaces.append(interface_name)
                                  table_data.extend([f"{node_name}_interfaces", format_list_with_newlines(node_interfaces)])
                      elif key_path[0] == "vsites":
                          table_data.extend(["add_section_title_virtual_sites", "virtual_sites"])
                          table_data.extend([f"virtual_sites_count", len(data.get(key_path[0]) if data.get(key_path[0]) is not None else [])])
                          table_data.extend([f"virtual_sites", format_list_with_newlines(data.get(key_path[0]))])
                      elif key_path[0] == "origin_pools":
                          origin_pool_count = 0
                          for namespace, values in data.items():
                              table_data.extend(["add_section_title_op", "origin_pools"])
                              for item, item_values in values.items():
                                  if item == "origin_pools":
                                      origin_pools = values.get(key_path[0])
                                      origin_pool_count = origin_pool_count + len(origin_pools.keys())
                                      table_data.extend([f"origin_pool_count", origin_pool_count])
                                      table_data.extend([f"{namespace}[origin_pools]", format_list_with_newlines(list(origin_pools.keys()))])
                      elif key_path[0] == "loadbalancer":
                          load_balancer_count = 0
                          for namespace, values in data.items():
                              table_data.extend(["add_section_title_lb", "load_balancer"])
                              for item, item_values in values.items():
                                  if item == "loadbalancer":
                                      for lb_type, load_balancer in item_values.items():
                                          load_balancer_count = load_balancer_count + len(load_balancer.keys())
                                          table_data.extend([f"load_balancer_count", load_balancer_count])
                                          table_data.extend([f"{namespace}[load_balancer][{lb_type}]", format_list_with_newlines(list(load_balancer.keys()))])
                      elif key_path[0] == "proxys":
                          proxys_count = 0
                          for namespace, values in data.items():
                              table_data.extend(["add_section_title_proxys", "proxys"])
                              for item, item_values in values.items():
                                  if item == "proxys":
                                      proxys_count = proxys_count + len(item_values.keys())
                                      table_data.extend([f"proxys_count", proxys_count])
                                      table_data.extend([f"{namespace}[proxys]", format_list_with_newlines(list(item_values.keys()))])
                      elif key_path[0] == "dc_cluster_group":
                          table_data.extend(["add_section_title_dc_cluster_group", "dc_cluster_group"])
                          table_data.extend([f"dc_cluster_group", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                      elif key_path[0] == "smg":
                          table_data.extend(["add_section_title_smg", "site_mesh_group"])
                          table_data.extend([f"smg_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                          table_data.extend([f"smg", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                      elif key_path[0] == "efp":
                          table_data.extend(["add_section_title_efp", "enhanced_firewall_policy"])
                          table_data.extend([f"efp_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                          table_data.extend([f"efp", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                      elif key_path[0] == "fpp":
                          table_data.extend(["add_section_title_fpp", "forward_proxy_policy"])
                          table_data.extend([f"fpp_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                          table_data.extend([f"fpp", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                      elif key_path[0] == "bgp":
                          table_data.extend(["add_section_title_bgp", "bgp"])
                          table_data.extend([f"bgp_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                          table_data.extend([f"bgp", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                      elif key_path[0] == "segments":
                          table_data.extend(["add_section_title_segments", "segments"])
                          table_data.extend([f"segments_count", len(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else {})])
                          table_data.extend([f"segments", format_list_with_newlines(list(data.get(key_path[0]).keys()) if data.get(key_path[0]) is not None else None)])
                      else:
                          table_data.extend([key_path[0], data.get(key_path[0])])

              for allowed_path in compare_paths:
                  p = allowed_path.split("/")
                  recurse(p, data_source[c.SITES_KEY][source], source_table_data)
                  recurse(p, data_target[c.SITES_KEY][target], target_table_data)

              # Convert flat lists into ordered Dictionaries (using OrderedDict for robustness across Python versions)
              # The slicing [::2] gets keys, [1::2] gets values. zip combines them into (key, value) pairs.
              source_dict = OrderedDict(zip(source_table_data[0::2], source_table_data[1::2]))
              target_dict = OrderedDict(zip(target_table_data[0::2], target_table_data[1::2]))

              self.logger.debug(source_dict)
              self.logger.debug(target_dict)

              # Build the final result list using the unified keys
              placeholder = 'N/A'

              # Master Key Liste generieren
              source_keys = list(source_dict.keys())
              target_keys = list(target_dict.keys())
              final_master_keys = build_master_key_list(source_keys, target_keys)

              for key in final_master_keys:
                  val1 = source_dict.get(key, placeholder)
                  val2 = target_dict.get(key, placeholder)

                  if key.startswith("add_section_title_"):
                      table.add_divider()
                  else:
                      table.add_row([key, val1, val2])
              """