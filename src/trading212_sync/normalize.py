"""Normalize Trading 212 responses into a compact portfolio snapshot."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

_T212_SUFFIX = re.compile(r"^(?P<ticker>.+)_[A-Z]{2}_EQ$")


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _percent(numerator: Any, denominator: Any) -> float | None:
    top = _number(numerator)
    bottom = _number(denominator)
    if top is None or bottom in (None, 0):
        return None
    return round(top / bottom * 100, 6)


def clean_ticker(trading212_ticker: Any) -> str | None:
    if not isinstance(trading212_ticker, str) or not trading212_ticker:
        return None
    match = _T212_SUFFIX.fullmatch(trading212_ticker)
    return match.group("ticker") if match else trading212_ticker


def normalize_account(raw: dict[str, Any]) -> dict[str, Any]:
    cash = _dict(raw.get("cash"))
    investments = _dict(raw.get("investments"))
    return {
        "currency": raw.get("currency") if isinstance(raw.get("currency"), str) else None,
        "total_value": _number(raw.get("totalValue")),
        "cash": _number(cash.get("availableToTrade")),
        "cash_in_pies": _number(cash.get("inPies")),
        "cash_reserved_for_orders": _number(cash.get("reservedForOrders")),
        "invested_value": _number(investments.get("currentValue")),
        "investment_cost": _number(investments.get("totalCost")),
        "realized_pnl": _number(investments.get("realizedProfitLoss")),
        "unrealized_pnl": _number(investments.get("unrealizedProfitLoss")),
    }


def normalize_position(raw: dict[str, Any], total_value: Any) -> dict[str, Any]:
    instrument = _dict(raw.get("instrument"))
    wallet = _dict(raw.get("walletImpact"))
    trading212_ticker = instrument.get("ticker") or raw.get("ticker")
    current_value = _number(wallet.get("currentValue"))
    total_cost = _number(wallet.get("totalCost"))
    unrealized_pnl = _number(wallet.get("unrealizedProfitLoss"))
    return {
        "ticker": clean_ticker(trading212_ticker),
        "trading212_ticker": trading212_ticker if isinstance(trading212_ticker, str) else None,
        "name": instrument.get("name") if isinstance(instrument.get("name"), str) else None,
        "isin": instrument.get("isin") if isinstance(instrument.get("isin"), str) else None,
        "currency": (
            instrument.get("currency") if isinstance(instrument.get("currency"), str) else None
        ),
        "value_currency": (
            wallet.get("currency") if isinstance(wallet.get("currency"), str) else None
        ),
        "quantity": _number(raw.get("quantity")),
        "quantity_available": _number(raw.get("quantityAvailableForTrading")),
        "quantity_in_pies": _number(raw.get("quantityInPies")),
        "average_price": _number(raw.get("averagePricePaid")),
        "current_price": _number(raw.get("currentPrice")),
        "current_value": current_value,
        "total_cost": total_cost,
        "unrealized_pnl": unrealized_pnl,
        "fx_impact": _number(wallet.get("fxImpact")),
        "unrealized_pnl_pct": _percent(unrealized_pnl, total_cost),
        "portfolio_weight_pct": _percent(current_value, total_value),
        "opened_at": raw.get("createdAt") if isinstance(raw.get("createdAt"), str) else None,
    }


def normalize_order(raw: dict[str, Any]) -> dict[str, Any]:
    instrument = _dict(raw.get("instrument"))
    trading212_ticker = raw.get("ticker") or instrument.get("ticker")
    return {
        "id": raw.get("id") if isinstance(raw.get("id"), (int, str)) else None,
        "ticker": clean_ticker(trading212_ticker),
        "trading212_ticker": trading212_ticker if isinstance(trading212_ticker, str) else None,
        "name": instrument.get("name") if isinstance(instrument.get("name"), str) else None,
        "instrument_currency": (
            instrument.get("currency") if isinstance(instrument.get("currency"), str) else None
        ),
        "order_currency": raw.get("currency") if isinstance(raw.get("currency"), str) else None,
        "type": raw.get("type") if isinstance(raw.get("type"), str) else None,
        "side": raw.get("side") if isinstance(raw.get("side"), str) else None,
        "status": raw.get("status") if isinstance(raw.get("status"), str) else None,
        "quantity": _number(raw.get("quantity")),
        "filled_quantity": _number(raw.get("filledQuantity")),
        "value": _number(raw.get("value")),
        "filled_value": _number(raw.get("filledValue")),
        "limit_price": _number(raw.get("limitPrice")),
        "stop_price": _number(raw.get("stopPrice")),
        "created_at": next(
            (
                value
                for value in (raw.get("createdAt"), raw.get("dateCreated"))
                if isinstance(value, str)
            ),
            None,
        ),
        "time_in_force": (
            raw.get("timeInForce") if isinstance(raw.get("timeInForce"), str) else None
        ),
        "extended_hours": (
            raw.get("extendedHours") if isinstance(raw.get("extendedHours"), bool) else None
        ),
    }


def normalize_historical_order(raw: dict[str, Any]) -> dict[str, Any]:
    # The official schema nests order/fill details. Fall back to a flat item to
    # remain compatible with beta API schema changes without inventing values.
    order = _dict(raw.get("order")) or raw
    fill = _dict(raw.get("fill"))
    fill_wallet = _dict(fill.get("walletImpact"))
    normalized = normalize_order(order)
    return {
        "activity_type": "order",
        **normalized,
        "status": normalized["status"] or (
            raw.get("status") if isinstance(raw.get("status"), str) else None
        ),
        "filled_at": next(
            (
                value
                for value in (
                    fill.get("filledAt"),
                    fill.get("dateTime"),
                    raw.get("filledAt"),
                    raw.get("dateTime"),
                )
                if isinstance(value, str)
            ),
            None,
        ),
        "fill_price": _number(fill.get("price") if fill else raw.get("fillPrice")),
        "fill_quantity": _number(fill.get("quantity")),
        "fill_currency": (
            fill_wallet.get("currency")
            if isinstance(fill_wallet.get("currency"), str)
            else None
        ),
        "fill_net_value": _number(fill_wallet.get("netValue")),
        "fill_fx_rate": _number(fill_wallet.get("fxRate")),
        "realized_pnl": _number(fill_wallet.get("realisedProfitLoss")),
    }


def normalize_transaction(raw: dict[str, Any]) -> dict[str, Any]:
    timestamp = next(
        (
            value
            for value in (raw.get("dateTime"), raw.get("time"), raw.get("createdAt"))
            if isinstance(value, str)
        ),
        None,
    )
    return {
        "activity_type": "transaction",
        "type": raw.get("type") if isinstance(raw.get("type"), str) else None,
        "timestamp": timestamp,
        "amount": _number(raw.get("amount")),
        "currency": raw.get("currency") if isinstance(raw.get("currency"), str) else None,
        "reference": raw.get("reference") if isinstance(raw.get("reference"), str) else None,
    }


def _activity_timestamp(item: dict[str, Any]) -> str:
    for key in ("filled_at", "timestamp", "created_at"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


def build_snapshot(
    account_raw: dict[str, Any],
    positions_raw: list[dict[str, Any]],
    pending_orders_raw: list[dict[str, Any]],
    historical_orders_raw: list[dict[str, Any]],
    transactions_raw: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
    history_status: dict[str, str] | None = None,
) -> dict[str, Any]:
    account = normalize_account(account_raw)
    positions = [normalize_position(item, account["total_value"]) for item in positions_raw]
    positions.sort(
        key=lambda item: item["current_value"] if item["current_value"] is not None else -1,
        reverse=True,
    )
    pending_orders = [normalize_order(item) for item in pending_orders_raw]
    recent_activity = [normalize_historical_order(item) for item in historical_orders_raw]
    recent_activity.extend(normalize_transaction(item) for item in transactions_raw)
    recent_activity.sort(key=_activity_timestamp, reverse=True)

    weighted_positions = [
        item for item in positions if item.get("portfolio_weight_pct") is not None
    ]
    largest = max(weighted_positions, key=lambda item: item["portfolio_weight_pct"], default=None)
    timestamp = generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")

    return {
        "generated_at": timestamp,
        "source": "Trading 212",
        "environment": "live",
        "account": account,
        "positions": positions,
        "pending_orders": pending_orders,
        "recent_activity": recent_activity,
        "derived": {
            "cash_weight_pct": _percent(account["cash"], account["total_value"]),
            "invested_weight_pct": _percent(
                account["invested_value"], account["total_value"]
            ),
            "largest_position": (
                {"ticker": largest["ticker"], "weight_pct": largest["portfolio_weight_pct"]}
                if largest
                else None
            ),
        },
        "sync_status": {
            "core": "ok",
            "historical_orders": (history_status or {}).get("historical_orders", "ok"),
            "transactions": (history_status or {}).get("transactions", "ok"),
        },
    }
