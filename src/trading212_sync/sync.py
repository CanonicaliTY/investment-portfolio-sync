"""Orchestrate fetching, normalization, and safe snapshot writing."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .client import APIError, Trading212Client
from .normalize import build_snapshot


def collect_snapshot(
    client: Trading212Client, *, history_limit: int = 100
) -> dict[str, Any]:
    account = client.account_summary()
    positions = client.positions()
    pending_orders = client.pending_orders()

    history_status: dict[str, str] = {}
    try:
        historical_orders = client.historical_orders(max_items=history_limit)
        history_status["historical_orders"] = "ok"
    except APIError as exc:
        historical_orders = []
        history_status["historical_orders"] = f"unavailable_http_{exc.status or 'error'}"

    try:
        transactions = client.transactions(max_items=history_limit)
        history_status["transactions"] = "ok"
    except APIError as exc:
        transactions = []
        history_status["transactions"] = f"unavailable_http_{exc.status or 'error'}"

    return build_snapshot(
        account,
        positions,
        pending_orders,
        historical_orders,
        transactions,
        history_status=history_status,
    )


def write_snapshot(snapshot: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(snapshot, temporary, indent=2, ensure_ascii=False, allow_nan=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, output_path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)

