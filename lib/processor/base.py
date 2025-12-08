import concurrent.futures
import re
from abc import abstractmethod, ABC
from logging import Logger
from typing import Any

from requests import Response, Session

import lib.const as c

FILTER_TYPE_1_AND_2 = "COMPARISON (Typ 1 oder 2)"
FILTER_TYPE_4 = "ASSIGNMENT (Typ 4)"
FILTER_TYPE_3 = "IN_LIST (Typ 3)"

COMPARISON_REGEX = re.compile(r"""
    ^\s* # Start with optional space
    (?P<key>[\w./-]+)                   # Key (e.g. ves.io/siteType)
    \s* # Optional space
    (?P<operator>[=!]=?)                # Operator (=, ==, oder !=)
    \s* # Optional space
    (?:                                 # Start of value alternatives
        '(?P<value_quoted>[\w./-]+)'    # Quoted Value (e.g. 'value')
    |
        (?P<value_unquoted>[\w./-]+)    # Unquoted Value (e.g. value)
    )
    \s*$                                # Optional space at the end
""", re.VERBOSE)

VALUE_PATTERN = r"(?:'[\w./-]+'|[\w./-]+)"  # Pattern for single value only quoted oder unquoted

IN_LIST_REGEX = re.compile(r"""
    ^\s* # Start with optional space
    (?P<key>[\w./-]+)                   # Key
    \s+in\s+                            # 'in' Operator
    \(                                  # Opening brace
        (?P<list_content>
            """ + VALUE_PATTERN + r""" # first element
            (?:,\s*""" + VALUE_PATTERN + r""")* # Null or more elements
        )
    \)
    \s*$                                # Optional space at the end
""", re.VERBOSE)


def _parse_single_filter(filter_string):
    """
    Try to parse a single filter expression  (Type1, Type2, Type3 or Type4)
    """

    # Try IN-LIST-REGEX (Typ 3)
    match_in = IN_LIST_REGEX.match(filter_string)
    if match_in:
        data = match_in.groupdict()
        list_content = data['list_content']

        # Extract quoted or unquoted values. Search for quoted or unquoted string
        # and store into separate capture groups
        value_pattern_for_extract = r"'([\w./-]+)'|([\w./-]+)"
        extracted = re.findall(value_pattern_for_extract, list_content)

        # 'extracted' is a list of tuples, e.g.[('valueA', ''), ('', 'valueB')].
        # Always choose the none empty string out of the tuple.
        values = [q or u for q, u in extracted]

        return {
            "filter_type": FILTER_TYPE_3,
            "key": data['key'],
            "operator": "in",
            "values": values
        }

    # Try COMPARISON_REGEX (Typ 1, 2 & 4)
    match_comp = COMPARISON_REGEX.match(filter_string)
    if match_comp:
        data = match_comp.groupdict()
        operator = data['operator']

        # Process if value is quoted or unquoted
        is_quoted = data['value_quoted'] is not None
        value = data['value_quoted'] if is_quoted else data['value_unquoted']

        filter_type = FILTER_TYPE_1_AND_2
        if operator == '=':
            filter_type = FILTER_TYPE_4

        return {
            "filter_type": filter_type,
            "key": data['key'],
            "operator": operator,
            "value": value,
            "value_quoted": is_quoted
        }

    # If there is no match
    return {"filter_type": "INVALID", "input": filter_string}


def _split_filter_string(full_string: str):
    """
    Split a filter string into individual filters expressions
    and ignore comma inside braces.
    """
    parts = []
    balance = 0
    start_index = 0

    for i, char in enumerate(full_string):
        if char == '(':
            balance += 1
        elif char == ')':
            balance -= 1
        # Do not ignore comma inside quotes ('....') since IN-List-Type is this only filter type which allows for comma inside braces.
        elif char == ',' and balance == 0:
            # Comma outside of braces found (Seperator for Type 4 filter expression)
            parts.append(full_string[start_index:i].strip())
            start_index = i + 1

    # add last part
    if start_index < len(full_string):
        parts.append(full_string[start_index:].strip())

    return parts


class Base(ABC):
    def __init__(self, session: Session = None, api_url: str = None, data: dict = None, site: str = None, workers: int = 10, logger: Logger = None):
        self._session = session
        self.api_url = api_url
        self._site = site
        self._urls = list()
        self._data = data
        self._workers = workers
        self._logger = logger
        self.must_break = False

    @property
    def urls(self):
        return self._urls

    @property
    def data(self):
        return self._data

    @property
    def site(self):
        return self._site

    @property
    def session(self):
        return self._session

    @property
    def workers(self):
        return self._workers

    @property
    def logger(self):
        return self._logger

    @urls.setter
    def urls(self, urls: list):
        self._urls = urls

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return f"class: {self.__class__.__name__}, api_url: {self.api_url}, site: {self._site}, workers: {self.workers}"

    def get_site_member_of_virtual_sites(self, site: str) -> set | None:
        """
        Evaluate site_selector expression in virtual site data
        Split expression into key, operator, value parts. If value is a comma separated list of items split these
        Compare site label and key with virtual site expression key and value. Supported comparators are "equal" and "in"

        Parameters
        ----------
        site string: Site name to check for virtual sites

        Returns
        -------
        A set of virtual sites a site is member of
        """

        # Store virtual sites current site is a member of
        site_is_member_of_virtual_sites = set()


        def _process_site(_filter: dict):
            for label, value in self.data["sites"][site]["metadata"]["labels"].items():
                #print("Label:", label)
                #print("Value:", value)
                #print(_filter)
                if label == _filter["key"] and value == _filter["value"]:
                    site_is_member_of_virtual_sites.add(vs_attr["metadata"]["name"])
                #for expression in filter:
                   # if label == expression["key"] and value == expression["value"]:
                   #     site_is_member_of_virtual_sites.add(vs_attr["metadata"]["name"])
                   # elif label == expression["key"] and value in expression["value"]:
                    #    if site == "aswins-test-smg-ce1":
                    #        pass
                            # print("LABEL:", label, "==", "expression[key]:", expression["key"])
                            # print("VALUE:", value, "==", "expression[value]", expression["value"])
                        # print(vs_attr["metadata"]["name"])
                        # site_is_member_of_virtual_sites.add(vs_attr["metadata"]["name"])

        for vs_name, vs_attr in self.data[c.VIRTUAL_SITES_KEY].items():
            _expressions = list()

            for exp in vs_attr["spec"]["site_selector"]["expressions"]:
                if site == "aswins-test-smg-ce1":
                    #self.logger.info("#" * 80)

                    # Split into single expression each
                    individual_filters = _split_filter_string(exp)

                    #self.logger.info(f"-> Found individual filter ({len(individual_filters)}): {individual_filters}")
                    #self.logger.info("-" * 80)

                    parsed_results = []
                    for i, filter_str in enumerate(individual_filters):
                        result = _parse_single_filter(filter_str)
                        parsed_results.append(result)

                        self.logger.info(f"--- Filter: {i + 1} ---")
                        #self.logger.info(f"INPUT: {filter_str}")

                        for k, v in result.items():
                            self.logger.debug(f"  {k.ljust(15)}: {v}")

                    #print(parsed_results)
                    for label, value in self.data["sites"][site]["metadata"]["labels"].items():
                        # print("Label:", label)
                        # print("Value:", value)
                        # print(_filter)
                        for _filter in parsed_results:
                            if _filter['filter_type'] == FILTER_TYPE_1_AND_2:
                                if label == _filter["key"] and value in _filter["value"]:
                                    site_is_member_of_virtual_sites.add(vs_attr["metadata"]["name"])
                            elif _filter['filter_type'] == FILTER_TYPE_3:
                                if label == _filter["key"] and value in _filter["values"]:
                                    site_is_member_of_virtual_sites.add(vs_attr["metadata"]["name"])
                            elif _filter['filter_type'] == FILTER_TYPE_4:
                                pass
                            #    if v == FILTER_TYPE_1_AND_2:
                            #        pass
                            # print("------------------------ Filter TYPE 1 or Type 2 -------------------------")
                            #    elif v == FILTER_TYPE_3:
                            #        pass
                            # print("------------------------ Filter TYPE 3 -------------------------")
                            #    elif v == FILTER_TYPE_4:
                            #        print("------------------------ Filter TYPE 4 -------------------------")
                            # self.logger.info(f"  {k.ljust(15)}: {v}")
                            #        self.logger.info(f"{result}")
                            # _process_site(result)
                            #print(_filter)
                            #print(_filter["key"], _filter["value"])
                            #if label == _filter["key"] and value == _filter["value"]:
                            #    site_is_member_of_virtual_sites.add(vs_attr["metadata"]["name"])

                    #self.logger.info("=" * 80)

        return site_is_member_of_virtual_sites

    def get_site_nic_mode(self, site: str = None) -> str | None:
        """
        Check if interface mode key exists in given data. Return site interface mode which is Single NIC or Dual NIC.
        "ingress_gw_ar" and "ingress_egress_ar" not supported. If mode is unknown return None
        :param site: the site name
        :return: return interface mode string
        """

        if "ingress_gw" in self.data[c.SITES_KEY][site][self.get_key_from_site_kind(site)]["spec"]:
            return "ingress_gw"
        elif "ingress_egress_gw" in self.data[c.SITES_KEY][site][self.get_key_from_site_kind(site)]["spec"]:
            return "ingress_egress_gw"
        else:
            self.logger.debug(f"Unsupported interface mode for site {site} found")
            return None

    def get_key_from_site_kind(self, site: str = None) -> str | None:
        """
        Returns key name according to site kind/type. Key name is used to create new key below site data structure.
        :param site: site name
        :return: key name
        """

        if self.data[c.SITES_KEY][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V1 or self.data[c.SITES_KEY][site]['kind'] == c.F5XC_SITE_TYPE_SMS_V2:
            return c.SITE_OBJECT_TYPE_SMS
        else:
            # F5XC_SITE_TYPE_AWS_TGW, F5XC_SITE_TYPE_AWS_VPC, F5XC_SITE_TYPE_AZURE_VNET, F5XC_SITE_TYPE_GCP_VPC
            return c.SITE_OBJECT_TYPE_LEGACY

    def get(self, url: str = None) -> Response | bool:
        """
        Run HTTP GET on a given url
        :param url: Actual URL to run GET request on
        :return: requests.Response
        """
        r = self.session.get(url)

        if 200 != r.status_code:
            self.logger.debug("get failed for {} with {}".format(url, r.status_code))
            return False

        return r if r else False

    def build_url(self, uri: str = None) -> str:
        """
        Build url from api url + resource uri
        :param uri: the resource uri
        :return: url string
        """
        return "{}{}".format(self.api_url, uri)

    def execute(self, name: str = None, urls: dict[str, Any] | list[str] = None) -> list | None:
        resp = list()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            self.logger.info(f"Prepare {name} query...")

            future_to_ds = {executor.submit(self.get, url=url): url for url in urls}
            for future in concurrent.futures.as_completed(future_to_ds):
                _data = future_to_ds[future]
                self.logger.info(f"process {name} get item: {future_to_ds[future]} ...")
                try:
                    data = future.result()
                except Exception as exc:
                    self.logger.info('%s: %r generated an exception: %s' % (f"process {name}", _data, exc))
                else:
                    self.logger.info(f"process {name} got item: {future_to_ds[future]} ...")
                    if data:
                        if isinstance(urls, dict):
                            resp.append({"object": urls[future_to_ds[future]], "data": data.json()})
                        elif isinstance(urls, list):
                            resp.append({future_to_ds[future]: data.json()["items"]}) if data and data.json()["items"] else None

            return resp

    @abstractmethod
    def run(self) -> dict:
        pass
