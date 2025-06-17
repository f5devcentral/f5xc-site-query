#!/usr/bin/env python3

"""
authors: cklewar
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from coloredlogs import ColoredFormatter

from lib.api import Api

# Configure the logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def main():
    # Create the parser
    parser = argparse.ArgumentParser(description="Get F5 XC Sites command line arguments")

    # Add arguments
    parser.add_argument('-a', '--apiurl', type=str, help='F5 XC API URL', required=False, default="")
    parser.add_argument('-c', '--compare', help='compare new site with old site', action='store_true')
    parser.add_argument('-f', '--file', type=str, help='read/write api data to/from json file', required=False, default=Path(__file__).stem + '.json')
    parser.add_argument('-n', '--namespace', type=str, help='namespace (not setting this option will process all namespaces)', required=False, default="")
    parser.add_argument('-q', '--query', help='run site query', action='store_true')
    parser.add_argument('-s', '--site', type=str, help='site to be processed', required=False, default="")
    parser.add_argument('-t', '--token', type=str, help='F5 XC API Token', required=False, default="")
    parser.add_argument('-w', '--workers', type=int, help='maximum number of worker for concurrent processing (default 10)', required=False, default=10)
    parser.add_argument('--old-site', help='old site name to compare with', required=False, default="")
    parser.add_argument('--new-site', help='new site name to compare with', required=False, default="")
    parser.add_argument('--old-site-file', help='new site file to compare with', required=False, default="")
    parser.add_argument('--new-site-file', help='new site file to compare with', required=False, default="")
    parser.add_argument('--build-inventory', help='build inventory and write it to file', action="store_true")
    parser.add_argument('--diff-table', help='print diff info to stdout', action='store_true')
    parser.add_argument('--diff-file-csv', help='write site diff info to csv file', required=False, default="")
    parser.add_argument('--inventory-table', help='print inventory info to stdout', action='store_true')
    parser.add_argument('--inventory-file-csv', help='write inventory info to csv file', required=False, default="")
    parser.add_argument('--log-level', type=str, help='set log level to INFO or DEBUG', required=False, default="INFO")
    parser.add_argument('--log-stdout', help='write log info to stdout', action='store_true')
    parser.add_argument('--log-file', help='write log info to file', action='store_true')

    # Parse the arguments
    args = parser.parse_args()

    if os.environ.get('GET-SITES-LOG-LEVEL'):
        level = getattr(logging, os.environ.get('GET-SITES-LOG-LEVEL').upper(), None)
    else:
        level = getattr(logging, args.log_level.upper(), logging.INFO)

    if not isinstance(level, int):
        raise ValueError('Invalid log level: %s' % os.environ.get('GET-SITES-LOG-LEVEL').upper())

    formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')

    if args.log_stdout:
        ch = logging.StreamHandler()
        ch.setLevel(level=level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    if args.log_file:
        fh = logging.FileHandler(args.log_file, "w", encoding="utf-8") if args.file is None else logging.FileHandler(Path(__file__).stem + '.log', "w", encoding="utf-8")
        fh.setLevel(level=level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    api_url = args.apiurl if args.apiurl else os.environ.get('f5xc_api_url')
    api_token = args.token if args.token else os.environ.get('f5xc_api_token')

    if not api_url or not api_token:
        logger.info("\n\n\n")
        logger.info(38 * "#")
        logger.info("api_url and api_token must be provided")
        logger.info(38 * "#")
        logger.info("\n\n\n")
        parser.print_help()
        sys.exit(1)

    logger.info(f"Application {os.path.basename(__file__)} started...")
    start_time = time.perf_counter()
    q = Api(logger=logger, api_url=api_url, api_token=api_token, namespace=args.namespace, site=args.site, workers=args.workers)

    if args.query:
        q.run()
        q.write_json_file(args.file)
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f'Query time: {int(elapsed_time)} seconds with {args.workers} workers')

    if args.compare:
        if args.old_site_file and args.new_site_file and args.old_site and args.new_site:
            data = q.compare(old_site=args.old_site, old_file=args.old_site_file, new_site=args.new_site, new_file=args.new_site_file)
            if data:
                logger.info(f"\n\n{data.get_formatted_string('text')}\n") if args.diff_table else None
                q.write_string_file(args.diff_file_csv, data.get_csv_string()) if args.diff_file_csv and data else None
        else:
            logger.info("Compare needs --old-site-file, --new-site-file, --new-site, --old-site options set")

    data = q.build_inventory(json_file=args.file) if args.build_inventory else None
    if data:
        q.write_string_file(args.inventory_file_csv, data.get_csv_string()) if args.inventory_file_csv and data else None
        logger.info(f"\n\n{data.get_formatted_string('text')}\n") if args.inventory_table else None
    logger.info(f"Application {os.path.basename(__file__)} finished")


if __name__ == '__main__':
    main()
