"""CLI entrypoint: reads an inventory workbook and pushes new objects into
a running NetBox instance via its REST API.

Usage:
    python -m netbox_import inventory.xlsx --dry-run
    python -m netbox_import inventory.xlsx
"""
from __future__ import annotations

import argparse
import os
import sys

import pynetbox

from .sync import run_sync
from .workbook import WorkbookError, load_workbook


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", help="Path to the inventory .xlsx file")
    parser.add_argument(
        "--url", default=os.environ.get("NETBOX_URL"), help="NetBox base URL (default: $NETBOX_URL)"
    )
    parser.add_argument(
        "--token", default=os.environ.get("NETBOX_TOKEN"), help="NetBox API token (default: $NETBOX_TOKEN)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would change without writing anything"
    )
    args = parser.parse_args(argv)

    if not args.url or not args.token:
        parser.error("NetBox URL and token are required (--url/--token or $NETBOX_URL/$NETBOX_TOKEN)")

    try:
        sheets = load_workbook(args.workbook)
    except WorkbookError as exc:
        parser.error(str(exc))

    if not sheets:
        print("No recognized sheets found in the workbook -- nothing to do.", file=sys.stderr)
        return 1

    nb = pynetbox.api(args.url, token=args.token)
    stats = run_sync(nb, sheets, dry_run=args.dry_run)
    print(("[DRY RUN] " if args.dry_run else "") + str(stats))
    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
