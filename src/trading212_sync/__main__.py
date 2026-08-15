"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import SyncError, Trading212Client
from .sync import collect_snapshot, write_snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync a read-only Trading 212 portfolio snapshot"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("portfolio/latest.json"),
        help="output JSON path (default: portfolio/latest.json)",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=100,
        help="maximum records per history type (default: 100)",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.history_limit < 0:
        print("Error: --history-limit cannot be negative.", file=sys.stderr)
        return 2
    try:
        client = Trading212Client.from_environment()
        snapshot = collect_snapshot(client, history_limit=args.history_limit)
        write_snapshot(snapshot, args.output)
    except SyncError as exc:
        print(f"Sync failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("Sync failed: could not safely write the portfolio snapshot.", file=sys.stderr)
        return 1

    print(f"Portfolio snapshot updated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
