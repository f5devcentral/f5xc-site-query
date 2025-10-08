"""
authors: cklewar
"""

import sys

from logging import Logger

from enlighten import get_manager
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.styles import Font
from openpyxl.styles import PatternFill

import lib.const as c

# CONSTS
GREY_FILL = PatternFill(start_color='778491', end_color='778491', fill_type='solid')
GREY_FILL_SECTION = PatternFill(start_color='99AABB', end_color='99AABB', fill_type='solid')
HEADER_FONT = Font(size=18, bold=True, italic=False, color="00000000")
SECTION_FONT = Font(size=14, bold=True, italic=False, color="00000001")
LIGHT_GREY_FILL = PatternFill(start_color='FFD9D9D9', end_color='FFD9D9D9', fill_type='solid')
RIGHT_ALIGNMENT = Alignment(horizontal='right')
WRAP_TEXT_RIGHT_ALIGNMENT = Alignment(horizontal='right', wrap_text=True)
LEFT_CENTER_ALIGNMENT = Alignment(horizontal='left', vertical='center')
LEFT_CENTER_WRAP_TEXT_ALIGNMENT = Alignment(horizontal='left', vertical='center', wrap_text=True)
HEADLINE_CELL_START = 'A1'
HEADLINE_CELLS = f'{HEADLINE_CELL_START}:F1'
COLUMN_DIMENSIONS_A_WIDTH = 30
COLUMN_DIMENSIONS_B_WIDTH = 25


class Xlsx(object):
    def __init__(self, site: str = None, file: str = None, data: dict = None, logger: Logger = None):
        self.logger = logger
        self.file = file
        self.wb = Workbook()
        self.ws = self.wb.active
        self.sites = data["site"]
        self.site = site
        self.must_break = False

    def write(self):
        self.wb.save(self.file)

    def build_summary(self, order: int = None):
        ws_summary = self.wb.create_sheet("Summary", order)

        # WS Summary Tab
        ws_summary.column_dimensions['A'].width = COLUMN_DIMENSIONS_A_WIDTH
        ws_summary.column_dimensions['B'].width = COLUMN_DIMENSIONS_B_WIDTH

        def process():
            pbar.update()

            table_data_infrastructure = [
                ("Kind", self.sites[site]["kind"]),
                ("Provider Type", self.sites[site]["metadata"]["labels"]["ves.io/provider"] if "ves.io/provider" in self.sites[site]["metadata"]["labels"] else "Unknown"),
                ("Main Node Count", self.sites[site]["main_node_count"]),
                ("Worker Node Count", self.sites[site]["worker_node_count"] if "worker_node_count" in self.sites[site] else 0),
                ("Node0 CPU Count", self.sites[site]["nodes"]["node0"]["hw_info"]["cpu"]["cpus"] if "hw_info" in self.sites[site]["nodes"]["node0"] else 0),
                ("Node0 Memory Size (MB)", self.sites[site]["nodes"]["node0"]["hw_info"]["memory"]["size_mb"] if "hw_info" in self.sites[site]["nodes"]["node0"] else 0),
                ("Node0 Interface Count", len(self.sites[site]["nodes"]["node0"]["interfaces"]) if "interfaces" in self.sites[site]["nodes"]["node0"] else 0),
            ]

            if "hw_info" in self.sites[site]["nodes"]["node0"]:
                for storage in self.sites[site]["nodes"]["node0"]["hw_info"]["storage"]:
                    node0_storage_size = storage["size_gb"]
                    table_data_infrastructure.append((f"Node0 Storage {storage["name"]} Size (GB)", node0_storage_size))

            if self.sites[site]["main_node_count"] > 1:
                table_data_infrastructure.extend(
                    [
                        ("Node1 CPU Count", self.sites[site]["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in self.sites[site]["nodes"]["node1"] else 0),
                        ("Node1 Memory Size (MB)", self.sites[site]["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] if "hw_info" in self.sites[site]["nodes"]["node1"] else 0),
                        ("Node1 Interface Count", len(self.sites[site]["nodes"]["node1"]["interfaces"]) if "interfaces" in self.sites[site]["nodes"]["node1"] else 0),
                    ]
                )

                if "hw_info" in self.sites[site]["nodes"]["node1"]:
                    for storage in self.sites[site]["nodes"]["node1"]["hw_info"]["storage"]:
                        node1_storage_size = storage["size_gb"]
                        table_data_infrastructure.append((f"Node1 Storage {storage["name"]} Size (GB)", node1_storage_size))

                table_data_infrastructure.extend(
                    [
                        ("Node2 CPU Count", self.sites[site]["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in self.sites[site]["nodes"]["node2"] else 0),
                        ("Node2 Memory Size (MB)", self.sites[site]["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] if "hw_info" in self.sites[site]["nodes"]["node2"] else 0),
                        ("Node2 Interface Count", len(self.sites[site]["nodes"]["node2"]["interfaces"]) if "interfaces" in self.sites[site]["nodes"]["node2"] else 0),
                    ]
                )

                if "hw_info" in self.sites[site]["nodes"]["node2"]:
                    for storage in self.sites[site]["nodes"]["node2"]["hw_info"]["storage"]:
                        node2_storage_size = storage["size_gb"]
                        table_data_infrastructure.append((f"Node2 Storage {storage["name"]} Size (GB)", node2_storage_size))

            lbs = 0
            ops = 0
            if "namespaces" in self.sites[site]:
                for item in self.sites[site]["namespaces"].values():
                    if "loadbalancer" in item.keys():
                        for lb_type in item["loadbalancer"].keys():
                            lbs = lbs + len(item["loadbalancer"][lb_type].keys())

                for item in self.sites[site]["namespaces"].values():
                    if "origin_pools" in item.keys():
                        ops = ops + len(item["origin_pools"].keys())

            table_data_services = [
                ('Count of LBs', lbs),
                ('Count of Origin pools', ops),
                ('Count of EFW', len(self.sites[site]["efp"].keys()) if "efp" in self.sites[site] else 0),
                ('Count of SMG', len(self.sites[site]["smg"].keys()) if "smg" in self.sites[site] else 0),
                ('Count of DCCG', len(self.sites[site]["dc_cluster_group"].keys()) if "dc_cluster_group" in self.sites[site] else 0),
                ('Count of Fast ACLs', ''),
                ('Count of segments', len(self.sites[site]["segments"].keys()) if "segments" in self.sites[site] else 0),
                ('Count of External Connectors', ''),
                ('Count of BGP Policies', len(self.sites[site]["bgp"].keys()) if "bgp" in self.sites[site] else 0),
                ('Count of BGP objects', '')
            ]

            ws_summary.append([f"Summary: {site}"])
            ws_summary.merge_cells(f"A{ws_summary.max_row}:F{ws_summary.max_row}")
            for cell in ws_summary[ws_summary.max_row]:
                cell.fill = GREY_FILL
                cell.font = HEADER_FONT
                cell.alignment = LEFT_CENTER_ALIGNMENT

            ### Infrastructure Section
            ws_summary.append(["Infrastructure", ""])

            for cell in ws_summary[ws_summary.max_row]:
                cell.fill = GREY_FILL_SECTION
                cell.font = SECTION_FONT

            header = ["Item", "Value"]
            ws_summary.append(header)

            for cell in ws_summary[ws_summary.max_row]:
                cell.fill = GREY_FILL_SECTION
                if cell.column != 1:
                    cell.alignment = RIGHT_ALIGNMENT

            append_count = 0
            for item, value in table_data_infrastructure:
                ws_summary.append([item, value])
                append_count = append_count + 1

            max_row = ws_summary.max_row
            if ws_summary.max_row % 2 == 0:
                max_row = ws_summary.max_row + 1

            for idx in range(ws_summary.max_row - append_count, max_row):
                value_cell = ws_summary[idx][1]
                value_cell.alignment = RIGHT_ALIGNMENT

                # Check if the row number is EVEN
                if idx % 2 == 0:
                    # Apply the grey fill to every cell in the current row
                    for cell in ws_summary[idx]:
                        cell.fill = LIGHT_GREY_FILL

            ### Services Section
            ws_summary.append(["Services", ""])

            for cell in ws_summary[ws_summary.max_row]:
                cell.fill = GREY_FILL_SECTION
                cell.font = SECTION_FONT

            header = ["Item", "Value"]
            ws_summary.append(header)

            for cell in ws_summary[ws_summary.max_row]:
                cell.fill = GREY_FILL_SECTION
                if cell.column != 1:
                    cell.alignment = RIGHT_ALIGNMENT

            append_count = 0
            for item, value in table_data_services:
                ws_summary.append([item, value])
                append_count += 1

            for idx in range(ws_summary.max_row - append_count, ws_summary.max_row + 1):
                value_cell = ws_summary[idx][1]
                value_cell.alignment = RIGHT_ALIGNMENT

                # Check if the row number is EVEN
                if idx % 2 == 0:
                    # Apply the grey fill to every cell in the current row
                    for cell in ws_summary[idx]:
                        cell.fill = LIGHT_GREY_FILL

        with get_manager() as manager:
            with manager.counter(total=None, desc='Processing summary for', unit='sites') as pbar:
                for site, site_data in self.sites.items():
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

    def build_infrastructure(self, order: int = None):
        # WS Infrastructure Tab
        ws_infrastructure = self.wb.create_sheet("Infrastructure", order)
        ws_infrastructure.column_dimensions['A'].width = 15
        ws_infrastructure.column_dimensions['B'].width = 25
        ws_infrastructure.column_dimensions['C'].width = 35
        ws_infrastructure.column_dimensions['F'].width = 40


        def process():
            pbar.update()

            ws_infrastructure.append([f"Infrastructure: {site}"])
            ws_infrastructure.merge_cells(f"A{ws_infrastructure.max_row}:F{ws_infrastructure.max_row}")

            for cell in ws_infrastructure[ws_infrastructure.max_row]:
                cell.fill = GREY_FILL
                cell.font = HEADER_FONT
                cell.alignment = LEFT_CENTER_ALIGNMENT

            append_count = 0
            for key, value in self.sites[site].items():
                if isinstance(value, str):
                    ws_infrastructure.append([key, value])
                    append_count = append_count + 1
                elif isinstance(value, int):
                    ws_infrastructure.append([key, value])
                    append_count = append_count + 1
                elif isinstance(value, dict):
                    if key in c.XLSX_INFRASTRUCTURE_EXPORT_KEYS:
                        if key == "spec":
                            if isinstance(value, dict):
                                for spec_key, spec_value in value.items():
                                    if isinstance(spec_value, str):
                                        if spec_value != "":
                                            ws_infrastructure.append([key, spec_key, spec_value])
                                            append_count = append_count + 1
                                    elif isinstance(spec_value, int):
                                        ws_infrastructure.append([key, spec_key, spec_value])
                                        append_count = append_count + 1
                                    elif isinstance(spec_value, list):
                                        for item in spec_value:
                                            if isinstance(value, dict):
                                                for k1, v1 in item.items():
                                                    if isinstance(spec_value, str):
                                                        if spec_value != "":
                                                            ws_infrastructure.append([key, spec_key, k1, v1])
                                                            append_count = append_count + 1
                                                    elif isinstance(spec_value, int):
                                                        ws_infrastructure.append([key, spec_key, k1, v1])
                                                        append_count = append_count + 1
                        elif key == "spoke":
                            if self.sites[site]["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                                # TODO add azure support
                                pass
                            elif self.sites[site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                                ws_infrastructure.append([key, len(value["vpc_list"])])
                                append_count = append_count + 1
                        elif key == "nodes":
                            for node, attrs in value.items():
                                if "interfaces" in attrs:
                                    ws_infrastructure.append(["node", node, "interfaces", len(attrs["interfaces"])])
                                    append_count = append_count + 1
                                if "hw_info" in attrs:
                                    for k, v in c.HW_INFO_ITEMS_TO_PROCESS.items():
                                        if k == "storage":
                                            for s in attrs["hw_info"][k]:
                                                for item in v:
                                                    if s[item] != 0:
                                                        ws_infrastructure.append(["node", node, "hw_info", k, s["name"], s[item]])
                                                        append_count = append_count + 1
                                        else:
                                            for item in v:
                                                ws_infrastructure.append(["node", node, "hw_info", k, item, attrs["hw_info"][k][item]])
                                                append_count = append_count + 1

            start = ws_infrastructure.max_row
            end = ws_infrastructure.max_row + 1

            if append_count > 1:
                start = ws_infrastructure.max_row - (append_count - 1)

            for idx in range(start, end):
                value_cell = ws_infrastructure[idx][1]
                value_cell.alignment = RIGHT_ALIGNMENT

                # Check if the row number is EVEN
                if append_count > 1:
                    if idx % 2 != 0:
                        # Apply the grey fill to every cell in the current row
                        for cell in ws_infrastructure[idx]:
                            cell.fill = LIGHT_GREY_FILL

        with get_manager() as manager:
            with manager.counter(total=None, desc='Processing infrastructure for', unit='sites') as pbar:
                for site, site_data in self.sites.items():
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

    def build_service(self, order: int = None):
        # WS Services Tab
        ws_services = self.wb.create_sheet("Services", order)
        ws_services.column_dimensions['A'].width = 10
        ws_services.column_dimensions['B'].width = 50
        ws_services.column_dimensions['C'].width = 15
        ws_services.column_dimensions['D'].width = 40
        ws_services.column_dimensions['F'].width = 60

        def process():
            pbar.update()

            ws_services.append([f"Services: {site}"])
            ws_services.merge_cells(f"A{ws_services.max_row}:F{ws_services.max_row}")

            for cell in ws_services[ws_services.max_row]:
                cell.fill = GREY_FILL
                cell.font = HEADER_FONT
                cell.alignment = LEFT_CENTER_ALIGNMENT

            append_count = 0
            for key, value in self.sites[site].items():
                if isinstance(value, dict):
                    if key in c.XLSX_SERVICE_EXPORT_KEYS:
                        if key == "spoke":
                            if self.sites[site]["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                                # TODO add azure support
                                pass
                            elif self.sites[site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                                ws_services.append([key, len(value["vpc_list"])])
                                append_count = append_count + 1
                        elif key == "namespaces":
                            for namespace, attrs in value.items():
                                for ns_item, ns_item_value in attrs.items():
                                    if ns_item == "loadbalancer":
                                        for lb, lb_values in ns_item_value.items():
                                            ws_services.append([key, namespace, ns_item, lb, "", '\n'.join(list(lb_values.keys())) if len(lb_values.keys()) > 1 else list(lb_values.keys())[0]])
                                            append_count = append_count + 1
                                    else:
                                        ws_services.append([key, namespace, ns_item, '\n'.join(list(ns_item_value.keys())) if len(ns_item_value.keys()) > 1 else list(ns_item_value.keys())[0],""])
                                        append_count = append_count + 1
                        else:
                            for name in value:
                                ws_services.append([key, name])
                                append_count = append_count + 1
                elif isinstance(value, list):
                    if len(value) > 0:
                        ws_services.append([key, ", ".join(value)])
                        append_count = append_count + 1

            start = ws_services.max_row
            end = ws_services.max_row + 1

            if append_count > 1:
                start = ws_services.max_row - (append_count - 1)

            for idx in range(start, end):
                value_cell = ws_services[idx][1]
                value_cell.alignment = RIGHT_ALIGNMENT

                # Check if the row number is EVEN
                if append_count > 1:
                    if idx % 2 != 0:
                        # Apply the grey fill to every cell in the current row
                        for cell in ws_services[idx]:
                            cell.fill = LIGHT_GREY_FILL

        with get_manager() as manager:
            with manager.counter(total=None, desc='Processing services for', unit='sites') as pbar:
                for site, site_data in self.sites.items():
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

    def build(self, site: str = None):
        self.build_summary(0)
        self.build_infrastructure(1)
        self.build_service(2)
