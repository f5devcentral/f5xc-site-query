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
    parser.add_argument('-c', '--csv-file', help='write inventory info to csv file', required=False, default="")
    parser.add_argument('-f', '--file', type=str, help='read/write api data to/from json file', required=False, default=Path(__file__).stem + '.json')
    parser.add_argument('-n', '--namespace', type=str, help='namespace (not setting this option will process all namespaces)', required=False, default="")
    parser.add_argument('-q', '--query', help='run site query', action='store_true')
    parser.add_argument('-s', '--site', type=str, help='site to be processed', required=False, default="")
    parser.add_argument('-t', '--token', type=str, help='F5 XC API Token', required=False, default="")
    parser.add_argument('-w', '--workers', type=int, help='maximum number of worker for concurrent processing (default 10)', required=False, default=10)
    parser.add_argument('--diff-file', type=str, help='compare to site', required=False, default="")
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
        parser.print_help()
        sys.exit(1)

    logger.info(f"Application {os.path.basename(__file__)} started...")
    start_time = time.perf_counter()
    q = Api(_logger=logger, api_url=api_url, api_token=api_token, namespace=args.namespace, site=args.site, workers=args.workers)

    if args.query:
        #q.run()
        #q.write_json_file(args.file)
        # q.compare(args.diff_file) if args.diff_file else None
        data = q.compare(old_file=args.diff_file, new_file=args.file) if args.diff_file else None
        #q.write_csv_file(args.csv_file, data) if args.csv_file and data else None
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f'Query time: {int(elapsed_time)} seconds with {args.workers} workers')

    q.write_csv_inventory(json_file=args.file, csv_file=args.csv_file) if args.csv_file and args.file else None
    logger.info(f"Application {os.path.basename(__file__)} finished")


if __name__ == '__main__':
    main()
