import json
import tempfile
import unittest
from pathlib import Path

from trading212_sync.client import APIError
from trading212_sync.sync import collect_snapshot, write_snapshot


class StubClient:
    def account_summary(self):
        return {"currency": "GBP", "totalValue": 100, "cash": {"availableToTrade": 100}}

    def positions(self):
        return []

    def pending_orders(self):
        return []

    def historical_orders(self, *, max_items):
        raise APIError("permission response must not be copied", status=403)

    def transactions(self, *, max_items):
        return [{"type": "DEPOSIT", "amount": 100, "currency": "GBP"}]


class SyncTests(unittest.TestCase):
    def test_optional_history_failure_does_not_break_core_snapshot(self) -> None:
        snapshot = collect_snapshot(StubClient())
        self.assertEqual(snapshot["sync_status"]["core"], "ok")
        self.assertEqual(snapshot["sync_status"]["historical_orders"], "unavailable_http_403")
        self.assertEqual(snapshot["sync_status"]["transactions"], "ok")
        self.assertEqual(len(snapshot["recent_activity"]), 1)
        self.assertNotIn("permission response", json.dumps(snapshot))

    def test_snapshot_is_written_as_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "latest.json"
            write_snapshot({"ok": True}, output)
            self.assertEqual(json.loads(output.read_text()), {"ok": True})
            self.assertFalse(any(output.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()

