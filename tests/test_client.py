import io
import json
import traceback
import unittest
from urllib.error import HTTPError

from trading212_sync.client import (
    APIError,
    MissingCredentialsError,
    Trading212Client,
    _RejectRedirects,
)


class FakeResponse(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class QueueOpener:
    def __init__(self, *results):
        self.results = list(results)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return FakeResponse(result)


class ClientTests(unittest.TestCase):
    def test_missing_credentials_fail_clearly(self) -> None:
        with self.assertRaises(MissingCredentialsError) as caught:
            Trading212Client("", "")
        self.assertIn("T212_API_KEY", str(caught.exception))
        self.assertIn("T212_API_SECRET", str(caught.exception))

    def test_only_get_is_used(self) -> None:
        opener = QueueOpener([])
        client = Trading212Client("key", "secret", opener=opener)
        self.assertEqual(client.positions(), [])
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 20.0)
        self.assertTrue(request.full_url.endswith("/equity/positions"))

    def test_pagination_follows_next_page_path_and_honors_limit(self) -> None:
        opener = QueueOpener(
            {
                "items": [{"id": 1}, {"id": 2}],
                "nextPagePath": "/api/v0/equity/history/orders?limit=2&cursor=abc",
            },
            {"items": [{"id": 3}, {"id": 4}], "nextPagePath": None},
        )
        client = Trading212Client("key", "secret", opener=opener)
        items = client.historical_orders(max_items=3)
        self.assertEqual([item["id"] for item in items], [1, 2, 3])
        self.assertIn("limit=3", opener.requests[0][0].full_url)
        self.assertIn("cursor=abc", opener.requests[1][0].full_url)

    def test_pagination_rejects_external_url(self) -> None:
        opener = QueueOpener(
            {"items": [], "nextPagePath": "https://attacker.example/steal"}
        )
        client = Trading212Client("key", "secret", opener=opener)
        with self.assertRaisesRegex(APIError, "untrusted"):
            client.transactions(max_items=10)

    def test_non_object_list_item_is_rejected(self) -> None:
        client = Trading212Client("key", "secret", opener=QueueOpener(["bad-item"]))
        with self.assertRaisesRegex(APIError, "list item"):
            client.positions()

    def test_pagination_rejects_repeated_cursor(self) -> None:
        repeated = "/api/v0/equity/history/transactions?limit=2&cursor=abc"
        opener = QueueOpener(
            {"items": [{"id": 1}], "nextPagePath": repeated},
            {"items": [{"id": 2}], "nextPagePath": repeated},
        )
        client = Trading212Client("key", "secret", opener=opener)
        with self.assertRaisesRegex(APIError, "repeated"):
            client.transactions(max_items=5)

    def test_api_error_never_includes_secret_or_response_body(self) -> None:
        api_key = "highly-sensitive-key"
        api_secret = "highly-sensitive-secret"
        body = io.BytesIO(f"server echoed {api_key}:{api_secret}".encode())
        error = HTTPError(
            "https://live.trading212.com/api/v0/equity/positions",
            401,
            f"bad secret {api_secret}",
            {},
            body,
        )
        client = Trading212Client(api_key, api_secret, opener=QueueOpener(error))

        status = None
        try:
            client.positions()
        except APIError as exc:
            rendered = "".join(traceback.format_exception(exc))
            status = exc.status
        else:
            self.fail("APIError was not raised")

        self.assertNotIn(api_key, rendered)
        self.assertNotIn(api_secret, rendered)
        self.assertNotIn("server echoed", rendered)
        self.assertEqual(status, 401)

    def test_rate_limit_is_retried_without_exposing_body(self) -> None:
        error = HTTPError(
            "https://live.trading212.com/api/v0/equity/orders",
            429,
            "rate limited",
            {"Retry-After": "2"},
            io.BytesIO(b"ignored"),
        )
        opener = QueueOpener(error, [])
        delays = []
        client = Trading212Client(
            "key", "secret", opener=opener, sleeper=delays.append, max_retries=1
        )
        self.assertEqual(client.pending_orders(), [])
        self.assertEqual(delays, [2.0])

    def test_private_request_guard_rejects_write_endpoint(self) -> None:
        client = Trading212Client("key", "secret", opener=QueueOpener({}))
        with self.assertRaisesRegex(APIError, "read-only allowlist"):
            client._get_json("/equity/orders/market", expected_type=dict)

    def test_redirects_are_rejected(self) -> None:
        handler = _RejectRedirects()
        self.assertIsNone(
            handler.redirect_request(
                None, None, 302, "Found", {}, "https://attacker.example"
            )
        )


if __name__ == "__main__":
    unittest.main()
