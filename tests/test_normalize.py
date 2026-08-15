import unittest

from trading212_sync.normalize import (
    build_snapshot,
    clean_ticker,
    normalize_historical_order,
    normalize_position,
)


class NormalizeTests(unittest.TestCase):
    def test_build_snapshot_normalizes_values_and_weights(self) -> None:
        snapshot = build_snapshot(
            {
                "currency": "GBP",
                "totalValue": 1_000,
                "cash": {
                    "availableToTrade": 200,
                    "inPies": 5,
                    "reservedForOrders": 10,
                },
                "investments": {
                    "currentValue": 800,
                    "totalCost": 700,
                    "realizedProfitLoss": 20,
                    "unrealizedProfitLoss": 100,
                },
            },
            [
                {
                    "averagePricePaid": 140,
                    "currentPrice": 160,
                    "quantity": 3,
                    "quantityAvailableForTrading": 2,
                    "quantityInPies": 1,
                    "createdAt": "2025-01-01T00:00:00Z",
                    "instrument": {
                        "ticker": "AAPL_US_EQ",
                        "name": "Apple",
                        "isin": "US0378331005",
                        "currency": "USD",
                    },
                    "walletImpact": {
                        "currency": "GBP",
                        "currentValue": 600,
                        "totalCost": 500,
                        "unrealizedProfitLoss": 100,
                        "fxImpact": 12.5,
                    },
                }
            ],
            [],
            [],
            [],
            generated_at="2025-01-02T00:00:00Z",
        )

        self.assertEqual(snapshot["account"]["cash"], 200)
        self.assertEqual(snapshot["account"]["invested_value"], 800)
        self.assertEqual(snapshot["positions"][0]["ticker"], "AAPL")
        self.assertEqual(snapshot["positions"][0]["trading212_ticker"], "AAPL_US_EQ")
        self.assertEqual(snapshot["positions"][0]["portfolio_weight_pct"], 60.0)
        self.assertEqual(snapshot["positions"][0]["unrealized_pnl_pct"], 20.0)
        self.assertEqual(snapshot["positions"][0]["value_currency"], "GBP")
        self.assertEqual(snapshot["positions"][0]["fx_impact"], 12.5)
        self.assertEqual(snapshot["derived"]["cash_weight_pct"], 20.0)
        self.assertEqual(snapshot["derived"]["invested_weight_pct"], 80.0)
        self.assertEqual(
            snapshot["derived"]["largest_position"],
            {"ticker": "AAPL", "weight_pct": 60.0},
        )

    def test_missing_fields_remain_null(self) -> None:
        position = normalize_position(
            {"instrument": {"ticker": "ODD-TICKER", "name": None}}, None
        )
        self.assertEqual(position["ticker"], "ODD-TICKER")
        self.assertIsNone(position["quantity"])
        self.assertIsNone(position["current_value"])
        self.assertIsNone(position["unrealized_pnl_pct"])
        self.assertIsNone(position["portfolio_weight_pct"])

    def test_ticker_cleanup_only_removes_known_suffix_shape(self) -> None:
        self.assertEqual(clean_ticker("BRK.B_US_EQ"), "BRK.B")
        self.assertEqual(clean_ticker("ABC_GB_EQ"), "ABC")
        self.assertEqual(clean_ticker("ABC_UNKNOWN"), "ABC_UNKNOWN")
        self.assertIsNone(clean_ticker(None))

    def test_zero_total_does_not_divide(self) -> None:
        snapshot = build_snapshot(
            {"totalValue": 0, "cash": {"availableToTrade": 0}},
            [],
            [],
            [],
            [],
        )
        self.assertIsNone(snapshot["derived"]["cash_weight_pct"])
        self.assertIsNone(snapshot["derived"]["largest_position"])

    def test_nested_historical_order_is_flattened(self) -> None:
        activity = normalize_historical_order(
            {
                "order": {
                    "id": 42,
                    "ticker": "MSFT_US_EQ",
                    "status": "FILLED",
                    "createdAt": "2025-01-01T10:00:00Z",
                },
                "fill": {
                    "filledAt": "2025-01-01T10:01:00Z",
                    "price": 400,
                    "quantity": 2,
                    "walletImpact": {
                        "currency": "GBP",
                        "netValue": 640,
                        "fxRate": 0.8,
                        "realisedProfitLoss": 25,
                    },
                },
            }
        )
        self.assertEqual(activity["ticker"], "MSFT")
        self.assertEqual(activity["filled_at"], "2025-01-01T10:01:00Z")
        self.assertEqual(activity["fill_quantity"], 2)
        self.assertEqual(activity["fill_currency"], "GBP")
        self.assertEqual(activity["realized_pnl"], 25)


if __name__ == "__main__":
    unittest.main()
