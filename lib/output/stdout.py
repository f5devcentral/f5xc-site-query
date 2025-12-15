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
                        if key in c.INVENTORY_EXPORT_KEYS:
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
                                        if site_data["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                                            interfaces = list()
                                            for interface in attrs['interfaces']:
                                                if "dedicated_interface" in interface.keys():
                                                    interfaces.append(interface['dedicated_interface']['device'])
                                                elif 'ethernet_interface' in interface.keys():
                                                    interfaces.append(interface['ethernet_interface']['device'])
                                            table.add_row([record_no, "node", node, "interfaces", len(interfaces), "", ", ".join(interfaces)])
                                        elif site_data["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                                            interfaces = list()
                                            for interface in attrs['interfaces']:
                                                if 'ethernet_interface' in interface.keys():
                                                    interfaces.append(interface['ethernet_interface']['device'])
                                            table.add_row([record_no, "node", node, "interfaces", len(interfaces), "", ", ".join(interfaces)])
                                        else:
                                            # Legacy Sites
                                            interfaces = list()
                                            if "slo" in attrs["interfaces"]:
                                                interfaces.append("slo")
                                            elif "sli" in attrs["interfaces"]:
                                                interfaces.append("sli")
                                            table.add_row([record_no, "node", node, "interfaces", len(interfaces), "", ", ".join(interfaces)])
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
                    self.table.add_row(service)

        self.logger.info(f"Stdout {self.build_comparison.__name__}. Done.")
        return self.table

    def _compare_interfaces(self, source: dict[str, Any] = None, target: dict[str, Any] = None) -> list[dict[str, Any]] | None:
        #######################################
        # Node0 Interfaces                    #
        #######################################
        if self.source_data and self.target_data:
            table_data_node_interfaces = list()
            source_node0_interfaces = list()
            target_node0_interfaces = list()

            if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                for interface in source["nodes"]["node0"]["interfaces"]:
                    if "dedicated_interface" in interface.keys():
                        source_node0_interfaces.append(interface["dedicated_interface"]["device"])
                    elif "ethernet_interface" in interface.keys():
                        source_node0_interfaces.append(interface["ethernet_interface"]["device"])
            else:
                # Legacy sites
                source_node0_interfaces.append(", ".join(source["nodes"]["node0"]["interfaces"].keys()))

            if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                target_node0_interfaces = [interface["name"] for interface in target["nodes"]["node0"]["interfaces"]]

            table_data_node_interfaces.append(["Node0 Interfaces", format_list_with_newlines(source_node0_interfaces), format_list_with_newlines(target_node0_interfaces)])

            #######################################
            # Node1 Interfaces                    #
            #######################################
            source_node1_interfaces = list()
            target_node1_interfaces = list()

            if source["main_node_count"] > 1 and target["main_node_count"] > 1:
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    for interface in source["nodes"]["node1"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            source_node1_interfaces.append(interface["dedicated_interface"]["device"])
                        elif "ethernet_interface" in interface.keys():
                            source_node1_interfaces.append(interface["ethernet_interface"]["device"])
                else:
                    # Legacy sites
                    source_node1_interfaces.append(", ".join(source["nodes"]["node1"]["interfaces"].keys()))

                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node1_interfaces = [interface["name"] for interface in target["nodes"]["node0"]["interfaces"]]

                table_data_node_interfaces.append(["Node1 Interfaces", format_list_with_newlines(source_node1_interfaces), format_list_with_newlines(target_node1_interfaces)])
            elif source["main_node_count"] > 2 < target["main_node_count"]:
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    for interface in source["nodes"]["node1"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            source_node1_interfaces.append(interface["dedicated_interface"]["device"])
                        elif "ethernet_interface" in interface.keys():
                            source_node1_interfaces.append(interface["ethernet_interface"]["device"])
                else:
                    # Legacy sites
                    source_node1_interfaces.append("".join(source["nodes"]["node1"]["interfaces"].keys()))
                table_data_node_interfaces.append(["Node1 Interfaces", source_node1_interfaces, PLACE_HOLDER])
            elif source["main_node_count"] <= 1 < target["main_node_count"]:
                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node1_interfaces = [interface["name"] for interface in target["nodes"]["node1"]["interfaces"]]
                table_data_node_interfaces.append(["Node1 Interfaces", PLACE_HOLDER, format_list_with_newlines(target_node1_interfaces)])

            #######################################
            # Node2 Interfaces                    #
            #######################################
            source_node2_interfaces = list()
            target_node2_interfaces = list()

            if source["main_node_count"] > 1 and target["main_node_count"] > 1:
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    for interface in source["nodes"]["node2"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            source_node2_interfaces.append(interface["dedicated_interface"]["device"])
                        elif "ethernet_interface" in interface.keys():
                            source_node2_interfaces.append(interface["ethernet_interface"]["device"])
                else:
                    # Legacy sites
                    source_node2_interfaces.append("".join(source["nodes"]["node2"]["interfaces"].keys()))

                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node2_interfaces = [interface["name"] for interface in target["nodes"]["node2"]["interfaces"]]

                table_data_node_interfaces.append(["Node2 Interfaces", format_list_with_newlines(source_node2_interfaces), format_list_with_newlines(target_node2_interfaces)])
            elif source["main_node_count"] > 2 < target["main_node_count"]:
                if source["kind"] == c.F5XC_SITE_TYPE_SMS_V1:
                    for interface in source["nodes"]["node2"]["interfaces"]:
                        if "dedicated_interface" in interface.keys():
                            source_node2_interfaces.append(interface["dedicated_interface"]["device"])
                        elif "ethernet_interface" in interface.keys():
                            source_node2_interfaces.append(interface["ethernet_interface"]["device"])
                    table_data_node_interfaces.append(["Node2 Interfaces", source_node2_interfaces, PLACE_HOLDER])
                else:
                    # Legacy sites
                    source_node2_interfaces.append("".join(source["nodes"]["node2"]["interfaces"].keys()))
                table_data_node_interfaces.append(["Node2 Interfaces", source_node2_interfaces, PLACE_HOLDER])
            elif source["main_node_count"] < 2 < target["main_node_count"]:
                if target["kind"] == c.F5XC_SITE_TYPE_SMS_V2:
                    target_node2_interfaces = [interface["name"] for interface in target["nodes"]["node2"]["interfaces"]]
                table_data_node_interfaces.append(["Node2 Interfaces", PLACE_HOLDER, target_node2_interfaces])

            self._data_interfaces = table_data_node_interfaces

            return self.data_interfaces
        else:
            return None
