"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import SyncError, Trading212Client
from .sync import collect_snapshot, write_snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读同步 Trading 212 投资组合快照")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("portfolio/latest.json"),
        help="输出 JSON 路径（默认：portfolio/latest.json）",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=100,
        help="每类历史记录最多读取条数（默认：100）",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.history_limit < 0:
        print("错误：--history-limit 不能为负数。", file=sys.stderr)
        return 2
    try:
        client = Trading212Client.from_environment()
        snapshot = collect_snapshot(client, history_limit=args.history_limit)
        write_snapshot(snapshot, args.output)
    except SyncError as exc:
        print(f"同步失败：{exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("同步失败：无法安全写入投资组合快照。", file=sys.stderr)
        return 1

    print(f"已更新投资组合快照：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

