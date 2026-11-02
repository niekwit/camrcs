"""Command line parser"""

import argparse

from camrcs import VERSION
from camrcs.download import down
from camrcs.manifest import rcs_manifest
from camrcs.upload import up
from camrcs.usage import usage


def main():
    parser = argparse.ArgumentParser(
        description="Management of data backups to/from Cambridge University Research Cold Storage (RCS)"
    )
    subparsers = parser.add_subparsers(dest="command")

    # up
    up_parser = subparsers.add_parser("up", help="Upload data to RCS")
    up_parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        help="Keep split archive files of target dir",
    )
    up_parser.add_argument(
        "-c",
        "--csv",
        action="store_true",
        help="Create empty data.csv file in current directory",
    )

    # down
    down_parser = subparsers.add_parser("down", help="Retrieve data from RCS")
    down_parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        help="Keep retrieved compressed archive after unpacking",
    )
    down_parser.add_argument(
        "-t", "--target", type=int, help="Target archive (id) to retrieve from RCS"
    )

    # usage
    subparsers.add_parser(
        "usage",
        help="Print how much data has been uploaded to RCS. "
        "Calculated from data.csv, not by connecting to the RCS server.",
    )

    # manifest
    subparsers.add_parser(
        "manifest",
        help="Create rcs_manifest.json with all entries uploaded to RCS. "
        "Calculated from data.csv, not by connecting to the RCS server.",
    )

    # version
    subparsers.add_parser("version", help="Print version and quit")

    args = parser.parse_args()

    if args.command == "up":
        up(args.csv, args.keep)
    elif args.command == "down":
        down(args.keep, args.target)
    elif args.command == "usage":
        usage()
    elif args.command == "manifest":
        rcs_manifest()
    elif args.command == "version":
        print(f"camrcs v{VERSION}")
    else:
        parser.print_help()
