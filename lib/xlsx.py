"""
authors: cklewar
"""

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
    """
    """

    def __init__(self, site: str = None, file: str = None, logger: Logger = None):
        """

        Parameters
        ----------
        site: str
        file: str
        logger: Logger
        """
        self.logger = logger
        self.file = file
        self.wb = Workbook()
        self.ws = self.wb.active
        self.site = site
        self.must_break = False

    def write(self):
        """

        Returns
        -------

        """
        self.wb.save(self.file)

    def build_inventory_summary(self, order: int = None, data: dict = None, title_prefix: str = None):
        """

        Parameters
        ----------
        order: int
        data: dict
        title_prefix: str

        Returns
        -------

        """

        sites = data["site"]

        # WS Summary Tab
        ws_summary = self.wb.create_sheet("Summary", order)
        ws_summary.column_dimensions['A'].width = COLUMN_DIMENSIONS_A_WIDTH
        ws_summary.column_dimensions['B'].width = COLUMN_DIMENSIONS_B_WIDTH

        def process():
            pbar.update()

            table_data_infrastructure = [
                ("Kind", sites[site]["kind"]),
                ("Provider Type", sites[site]["metadata"]["labels"]["ves.io/provider"] if "ves.io/provider" in sites[site]["metadata"]["labels"] else "Unknown"),
                ("Main Node Count", sites[site]["main_node_count"]),
                ("Worker Node Count", sites[site]["worker_node_count"] if "worker_node_count" in sites[site] else 0),
                ("Node0 CPU Count", sites[site]["nodes"]["node0"]["hw_info"]["cpu"]["cpus"] if "hw_info" in sites[site]["nodes"]["node0"] else 0),
                ("Node0 Memory Size (MB)", sites[site]["nodes"]["node0"]["hw_info"]["memory"]["size_mb"] if "hw_info" in sites[site]["nodes"]["node0"] else 0),
                ("Node0 Interface Count", len(sites[site]["nodes"]["node0"]["interfaces"]) if "interfaces" in sites[site]["nodes"]["node0"] else 0),
            ]

            if "hw_info" in sites[site]["nodes"]["node0"]:
                for storage in sites[site]["nodes"]["node0"]["hw_info"]["storage"]:
                    node0_storage_size = storage["size_gb"]
                    table_data_infrastructure.append((f"Node0 Storage {storage["name"]} Size (GB)", node0_storage_size))

            if sites[site]["main_node_count"] > 1:
                table_data_infrastructure.extend(
                    [
                        ("Node1 CPU Count", sites[site]["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in sites[site]["nodes"]["node1"] else 0),
                        ("Node1 Memory Size (MB)", sites[site]["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] if "hw_info" in sites[site]["nodes"]["node1"] else 0),
                        ("Node1 Interface Count", len(sites[site]["nodes"]["node1"]["interfaces"]) if "interfaces" in sites[site]["nodes"]["node1"] else 0),
                    ]
                )

                if "hw_info" in sites[site]["nodes"]["node1"]:
                    for storage in sites[site]["nodes"]["node1"]["hw_info"]["storage"]:
                        node1_storage_size = storage["size_gb"]
                        table_data_infrastructure.append((f"Node1 Storage {storage["name"]} Size (GB)", node1_storage_size))

                table_data_infrastructure.extend(
                    [
                        ("Node2 CPU Count", sites[site]["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in sites[site]["nodes"]["node2"] else 0),
                        ("Node2 Memory Size (MB)", sites[site]["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] if "hw_info" in sites[site]["nodes"]["node2"] else 0),
                        ("Node2 Interface Count", len(sites[site]["nodes"]["node2"]["interfaces"]) if "interfaces" in sites[site]["nodes"]["node2"] else 0),
                    ]
                )

                if "hw_info" in sites[site]["nodes"]["node2"]:
                    for storage in sites[site]["nodes"]["node2"]["hw_info"]["storage"]:
                        node2_storage_size = storage["size_gb"]
                        table_data_infrastructure.append((f"Node2 Storage {storage["name"]} Size (GB)", node2_storage_size))

            lbs = 0
            ops = 0
            if "namespaces" in sites[site]:
                for item in sites[site]["namespaces"].values():
                    if "loadbalancer" in item.keys():
                        for lb_type in item["loadbalancer"].keys():
                            lbs = lbs + len(item["loadbalancer"][lb_type].keys())

                for item in sites[site]["namespaces"].values():
                    if "origin_pools" in item.keys():
                        ops = ops + len(item["origin_pools"].keys())

            table_data_services = [
                ('Count of LBs', lbs),
                ('Count of Origin pools', ops),
                ('Count of EFW', len(sites[site]["efp"].keys()) if "efp" in sites[site] else 0),
                ('Count of SMG', len(sites[site]["smg"].keys()) if "smg" in sites[site] else 0),
                ('Count of DCCG', len(sites[site]["dc_cluster_group"].keys()) if "dc_cluster_group" in sites[site] else 0),
                ('Count of Fast ACLs', ''),
                ('Count of segments', len(sites[site]["segments"].keys()) if "segments" in sites[site] else 0),
                ('Count of External Connectors', ''),
                ('Count of BGP Policies', len(sites[site]["bgp"].keys()) if "bgp" in sites[site] else 0),
                ('Count of BGP objects', '')
            ]

            ws_summary.append([f"Summary: {site}"] if title_prefix is None else [f"{title_prefix}: {site}"])
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
                for site, site_data in sites.items():
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

    def build_inventory_infrastructure(self, order: int = None, data: dict = None):
        """

        Parameters
        ----------
        data : dict
        order: int

        Returns
        -------

        """

        sites = data["site"]

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
            for key, value in sites[site].items():
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
                            if sites[site]["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                                # TODO add azure support
                                pass
                            elif sites[site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
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
                for site, site_data in sites.items():
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

    def build_inventory_service(self, order: int = None, data: dict = None):
        """

        Parameters
        ----------
        data: dict
        order: int

        Returns
        -------

        """

        sites = data["site"]

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
            for key, value in sites[site].items():
                if isinstance(value, dict):
                    if key in c.XLSX_SERVICE_EXPORT_KEYS:
                        if key == "spoke":
                            if sites[site]["kind"] == c.F5XC_SITE_TYPE_AZURE_VNET:
                                # TODO add azure support
                                pass
                            elif sites[site]["kind"] == c.F5XC_SITE_TYPE_AWS_TGW:
                                ws_services.append([key, len(value["vpc_list"])])
                                append_count = append_count + 1
                        elif key == "namespaces":
                            for namespace, attrs in value.items():
                                for ns_item, ns_item_value in attrs.items():
                                    if ns_item == "loadbalancer":
                                        for lb, lb_values in ns_item_value.items():
                                            ws_services.append(
                                                [key, namespace, ns_item, lb, "", '\n'.join(list(lb_values.keys())) if len(lb_values.keys()) > 1 else list(lb_values.keys())[0]])
                                            append_count = append_count + 1
                                    else:
                                        ws_services.append(
                                            [key, namespace, ns_item, '\n'.join(list(ns_item_value.keys())) if len(ns_item_value.keys()) > 1 else list(ns_item_value.keys())[0],
                                             ""])
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
                for site, site_data in sites.items():
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

    def build_inventory(self, data: dict = None):
        """

        Parameters
        ----------
        data: dict

        Returns
        -------

        """

        self.build_inventory_summary(0, data)
        self.build_inventory_infrastructure(1, data)
        self.build_inventory_service(2, data)

    def build_compare_summary(self, order: int = None, summary_data: dict = None, data_source: dict = None, data_target: dict = None):
        """

        Parameters
        ----------
        order: int
        summary_data: dict
        data_source: dict
        data_target: dict

        Returns
        -------

        """

        # summary_data = dict()
        # summary_data["site"] = dict()
        # summary_data["site"][data_source["metadata"]["name"]] = data_source
        # summary_data["site"][data_target["metadata"]["name"]] = data_target
        # self.build_inventory_summary(0, data=summary_data)

        # WS Summary Comparison Tab
        ws_summary = self.wb.create_sheet("Summary", order)
        ws_summary.column_dimensions['A'].width = 25
        ws_summary.column_dimensions['B'].width = 30
        ws_summary.column_dimensions['C'].width = 30

        table_data_infrastructure = [
            ("Kind", data_source["kind"], data_target["kind"]),
            ("Provider Type", data_source["metadata"]["labels"]["ves.io/provider"] if "ves.io/provider" in data_source["metadata"]["labels"] else "Unknown",
             data_target["metadata"]["labels"]["ves.io/provider"] if "ves.io/provider" in data_target["metadata"]["labels"] else "Unknown"),
            ("Main Node Count", data_source["main_node_count"], data_target["main_node_count"]),
            ("Worker Node Count", data_source["worker_node_count"] if "worker_node_count" in data_source else 0,
             data_target["worker_node_count"] if "worker_node_count" in data_target else 0),
            ("Node0 CPU Count", data_source["nodes"]["node0"]["hw_info"]["cpu"]["cpus"] if "hw_info" in data_source["nodes"]["node0"] else 0,
             data_target["nodes"]["node0"]["hw_info"]["cpu"]["cpus"] if "hw_info" in data_target["nodes"]["node0"] else 0),
            ("Node0 Memory Size (MB)", data_source["nodes"]["node0"]["hw_info"]["memory"]["size_mb"] if "hw_info" in data_source["nodes"]["node0"] else 0,
             data_target["nodes"]["node0"]["hw_info"]["memory"]["size_mb"] if "hw_info" in data_target["nodes"]["node0"] else 0),
            ("Node0 Interface Count", len(data_source["nodes"]["node0"]["interfaces"]) if "interfaces" in data_source["nodes"]["node0"] else 0,
             len(data_target["nodes"]["node0"]["interfaces"]) if "interfaces" in data_target["nodes"]["node0"] else 0)
        ]

        if "hw_info" in data_source["nodes"]["node0"] and "hw_info" in data_target["nodes"]["node0"]:
            for storage_source, storage_target in zip(data_source["nodes"]["node0"]["hw_info"]["storage"], data_target["nodes"]["node0"]["hw_info"]["storage"]):
                source_node0_storage_size = storage_source["size_gb"]
                target_node0_storage_size = storage_target["size_gb"]
                table_data_infrastructure.append((f"Node0 Storage {storage_source["name"]} Size (GB)", source_node0_storage_size, target_node0_storage_size))

        if data_source["main_node_count"] > 1 and data_target["main_node_count"] > 1:
            table_data_infrastructure.extend(
                [
                    ("Node1 CPU Count", data_source["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in data_source["nodes"]["node1"] else 0,
                     data_target["nodes"]["node1"]["hw_info"]["cpu"]["cpus"] if "hw_info" in data_target["nodes"]["node1"] else 0),
                    ("Node1 Memory Size (MB)", data_source["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] if "hw_info" in data_source["nodes"]["node1"] else 0,
                     data_target["nodes"]["node1"]["hw_info"]["memory"]["size_mb"] if "hw_info" in data_target["nodes"]["node1"] else 0),
                    ("Node1 Interface Count", len(data_source["nodes"]["node1"]["interfaces"]) if "interfaces" in data_source["nodes"]["node1"] else 0,
                     len(data_target["nodes"]["node1"]["interfaces"]) if "interfaces" in data_target["nodes"]["node1"] else 0),
                ]
            )

            if "hw_info" in data_source["nodes"]["node1"]:
                for storage_source, storage_target in zip(data_source["nodes"]["node1"]["hw_info"]["storage"], data_target["nodes"]["node1"]["hw_info"]["storage"]):
                    source_node1_storage_size = storage_source["size_gb"]
                    target_node1_storage_size = storage_target["size_gb"]
                    table_data_infrastructure.append((f"Node1 Storage {storage_source["name"]} Size (GB)", source_node1_storage_size, target_node1_storage_size))

            table_data_infrastructure.extend(
                [
                    ("Node2 CPU Count", data_source["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in data_source["nodes"]["node2"] else 0,
                     data_target["nodes"]["node2"]["hw_info"]["cpu"]["cpus"] if "hw_info" in data_target["nodes"]["node2"] else 0),
                    ("Node2 Memory Size (MB)", data_source["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] if "hw_info" in data_source["nodes"]["node2"] else 0,
                     data_target["nodes"]["node2"]["hw_info"]["memory"]["size_mb"] if "hw_info" in data_target["nodes"]["node2"] else 0),
                    ("Node2 Interface Count", len(data_source["nodes"]["node2"]["interfaces"]) if "interfaces" in data_source["nodes"]["node2"] else 0,
                     len(data_target["nodes"]["node2"]["interfaces"]) if "interfaces" in data_target["nodes"]["node2"] else 0),
                ]
            )

            if "hw_info" in data_source["nodes"]["node2"]:
                for storage_source, storage_target in zip(data_source["nodes"]["node2"]["hw_info"]["storage"], data_target["nodes"]["node2"]["hw_info"]["storage"]):
                    source_node2_storage_size = storage_source["size_gb"]
                    target_node2_storage_size = storage_target["size_gb"]
                    table_data_infrastructure.append((f"Node2 Storage {storage_source["name"]} Size (GB)", source_node2_storage_size, target_node2_storage_size))

        source_lbs = 0
        source_ops = 0
        target_lbs = 0
        target_ops = 0

        if "namespaces" in data_source:
            for source_item in data_source["namespaces"].values():
                if "loadbalancer" in source_item.keys():
                    for source_lb_type in source_item["loadbalancer"].keys():
                        source_lbs = source_lbs + len(source_item["loadbalancer"][source_lb_type].keys())

            for source_item in data_source["namespaces"].values():
                if "origin_pools" in source_item.keys():
                    source_ops = source_ops + len(source_item["origin_pools"].keys())

        if "namespaces" in data_target:
            for target_item in data_target["namespaces"].values():
                if "loadbalancer" in target_item.keys():
                    for target_lb_type in target_item["loadbalancer"].keys():
                        target_lbs = target_lbs + len(target_item["loadbalancer"][target_lb_type].keys())

            for target_item in data_target["namespaces"].values():
                if "origin_pools" in target_item.keys():
                    target_ops = target_ops + len(target_item["origin_pools"].keys())

        table_data_services = [
            ('Count of LBs', source_lbs, target_lbs),
            ('Count of Origin pools', source_ops, target_ops),
            ('Count of EFW', len(data_source["efp"].keys()) if "efp" in data_source else 0, len(data_target["efp"].keys()) if "efp" in data_target else 0),
            ('Count of SMG', len(data_source["smg"].keys()) if "smg" in data_source else 0, len(data_target["smg"].keys()) if "smg" in data_target else 0),
            ('Count of DCCG', len(data_source["dc_cluster_group"].keys()) if "dc_cluster_group" in data_source else 0,
             len(data_target["dc_cluster_group"].keys()) if "dc_cluster_group" in data_target else 0),
            ('Count of Fast ACLs', '', ''),
            ('Count of segments', len(data_source["segments"].keys()) if "segments" in data_source else 0, len(data_target["segments"].keys()) if "segments" in data_target else 0),
            ('Count of External Connectors', '', ''),
            ('Count of BGP Policies', len(data_source["bgp"].keys()) if "bgp" in data_source else 0, len(data_target["bgp"].keys()) if "bgp" in data_target else 0),
            ('Count of BGP objects', '', '')
        ]

        ws_summary.append([f"Summary comparison: {data_source["metadata"]["name"]} with {data_target["metadata"]["name"]}"])
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

        header = ["Item", "Source", "Target"]
        ws_summary.append(header)

        for cell in ws_summary[ws_summary.max_row]:
            cell.fill = GREY_FILL_SECTION
            if cell.column != 1:
                cell.alignment = RIGHT_ALIGNMENT

        append_count = 0
        for item, source, target in table_data_infrastructure:
            ws_summary.append([item, source, target])
            append_count = append_count + 1

        start = 4
        end = ws_summary.max_row + 1

        for idx in range(start, end):
            value_cell_source = ws_summary[idx][1]
            value_cell_target = ws_summary[idx][2]
            value_cell_source.alignment = RIGHT_ALIGNMENT
            value_cell_target.alignment = RIGHT_ALIGNMENT

            if value_cell_source.value != value_cell_target.value:
                value_cell_source.font = Font(color='FFFF0000', bold=False)
                value_cell_target.font = Font(color='FFFF0000', bold=False)

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

        header = ["Item", "Source", "Target"]
        ws_summary.append(header)

        for cell in ws_summary[ws_summary.max_row]:
            cell.fill = GREY_FILL_SECTION
            if cell.column != 1:
                cell.alignment = RIGHT_ALIGNMENT

        append_count = 0
        for item, source_value, target_value in table_data_services:
            ws_summary.append([item, source_value, target_value])
            append_count += 1

        for idx in range(ws_summary.max_row - append_count + 1, ws_summary.max_row + 1):
            value_cell_source = ws_summary[idx][1]
            value_cell_target = ws_summary[idx][2]
            value_cell_source.alignment = RIGHT_ALIGNMENT
            value_cell_target.alignment = RIGHT_ALIGNMENT

            if value_cell_source.value != value_cell_target.value:
                value_cell_source.font = Font(color='FFFF0000', bold=False)
                value_cell_target.font = Font(color='FFFF0000', bold=False)

            # Check if the row number is EVEN
            if idx % 2 == 0:
                # Apply the grey fill to every cell in the current row
                for cell in ws_summary[idx]:
                    cell.fill = LIGHT_GREY_FILL

    def build_compare_infrastructure(self, order: int = None, data: dict = None):
        """

        Parameters
        ----------
        order: int
        data: dict

        Returns
        -------

        """

        # WS Infrastructure Tab
        ws_infrastructure = self.wb.create_sheet("Infrastructure", order)
        ws_infrastructure.column_dimensions['A'].width = 40
        ws_infrastructure.column_dimensions['B'].width = 60

        ws_infrastructure.append([f"Infrastructure: Differences"])
        ws_infrastructure.merge_cells(f"A{ws_infrastructure.max_row}:F{ws_infrastructure.max_row}")

        for cell in ws_infrastructure[ws_infrastructure.max_row]:
            cell.fill = GREY_FILL
            cell.font = HEADER_FONT
            cell.alignment = LEFT_CENTER_ALIGNMENT

        items_to_process = ["kind", "metadata", "spec", "nodes"]
        for item in data:
            if isinstance(item, dict):
                if item["path"].split("/")[0] in items_to_process:
                    if isinstance(item["values"], str):
                        ws_infrastructure.append([item["path"], item["values"]])
                    elif isinstance(item["values"], int):
                        ws_infrastructure.append([item["path"], item["values"]])
                    elif isinstance(item["values"], list):
                        ws_infrastructure.append([item["path"], "\n".join(item["values"])])

        end = ws_infrastructure.max_row

        for idx in range(1, end):
            value_cell = ws_infrastructure[idx][1]
            value_cell.alignment = RIGHT_ALIGNMENT

            # Check if the row number is EVEN
            if idx % 2 != 0:
                # Apply the grey fill to every cell in the current row
                for cell in ws_infrastructure[idx]:
                    cell.fill = LIGHT_GREY_FILL

    def build_compare_service(self, order: int = None, data: dict = None):
        """

        Parameters
        ----------
        order: int
        data: dict

        Returns
        -------

        """

        # WS Infrastructure Tab
        ws_services = self.wb.create_sheet("Services", order)
        ws_services.column_dimensions['A'].width = 40
        ws_services.column_dimensions['B'].width = 60

        ws_services.append([f"Services: Differences"])
        ws_services.merge_cells(f"A{ws_services.max_row}:F{ws_services.max_row}")

        for cell in ws_services[ws_services.max_row]:
            cell.fill = GREY_FILL
            cell.font = HEADER_FONT
            cell.alignment = LEFT_CENTER_ALIGNMENT

        for item in data:
            if isinstance(item, dict):
                if item["path"].split("/")[0] == "None":
                    path = "/".join(item["path"].split("/")[1:])
                    service = item["path"].split("/")[1]
                else:
                    path = item["path"]
                    service = item["path"].split("/")[0]

                if service in c.XLSX_SERVICE_EXPORT_KEYS:
                    if isinstance(item["values"], str):
                        ws_services.append([path, item["values"]])
                    elif isinstance(item["values"], int):
                        ws_services.append([path, item["values"]])
                    elif isinstance(item["values"], list):
                        ws_services.append([path, "\n".join(item["values"])])

        end = ws_services.max_row

        for idx in range(1, end):
            value_cell = ws_services[idx][1]
            value_cell.alignment = RIGHT_ALIGNMENT

            # Check if the row number is EVEN
            if idx % 2 != 0:
                # Apply the grey fill to every cell in the current row
                for cell in ws_services[idx]:
                    cell.fill = LIGHT_GREY_FILL

    def build_compare(self, data: dict = None, data_source: dict = None, data_target: dict = None):
        """

        Parameters
        ----------
        data: dict
        data_source: dict
        data_target: dict

        Returns
        -------

        """

        self.build_compare_summary(0, data, data_source, data_target)
        self.build_compare_infrastructure(1, data)
        self.build_compare_service(2, data)
