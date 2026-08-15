"""A deliberately small, GET-only client for the Trading 212 Public API."""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

LIVE_BASE_URL = "https://live.trading212.com/api/v0"

# Security boundary: requests outside this exact read-only set are rejected.
ALLOWED_PATHS = frozenset(
    {
        "/equity/account/summary",
        "/equity/positions",
        "/equity/orders",
        "/equity/history/orders",
        "/equity/history/transactions",
    }
)


class _RejectRedirects(HTTPRedirectHandler):
    """Never forward the Basic Auth request to a redirected location."""

    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


_SAFE_OPENER = build_opener(_RejectRedirects()).open


class SyncError(RuntimeError):
    """Base class for safe, user-facing sync errors."""


class MissingCredentialsError(SyncError):
    """Raised when required environment variables are absent."""


class APIError(SyncError):
    """Raised for a sanitized API or transport failure."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Trading212Client:
    """Read data from the fixed Trading 212 live API.

    The class exposes no generic public request method and has no POST, PUT,
    PATCH, or DELETE implementation.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        timeout: float = 20.0,
        max_retries: int = 2,
        opener: Callable[..., Any] = _SAFE_OPENER,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key or not api_secret:
            raise MissingCredentialsError(
                "缺少 Trading 212 凭据；请设置 T212_API_KEY 和 T212_API_SECRET。"
            )
        self._authorization = self._build_authorization(api_key, api_secret)
        self._timeout = timeout
        self._max_retries = max_retries
        self._opener = opener
        self._sleep = sleeper

    @classmethod
    def from_environment(cls, **kwargs: Any) -> "Trading212Client":
        return cls(
            os.environ.get("T212_API_KEY", ""),
            os.environ.get("T212_API_SECRET", ""),
            **kwargs,
        )

    @staticmethod
    def _build_authorization(api_key: str, api_secret: str) -> str:
        token = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode("ascii")
        return f"Basic {token}"

    def account_summary(self) -> dict[str, Any]:
        return self._get_json("/equity/account/summary", expected_type=dict)

    def positions(self) -> list[dict[str, Any]]:
        return self._get_list("/equity/positions")

    def pending_orders(self) -> list[dict[str, Any]]:
        return self._get_list("/equity/orders")

    def historical_orders(self, *, max_items: int = 100) -> list[dict[str, Any]]:
        return self._paginated("/equity/history/orders", max_items=max_items)

    def transactions(self, *, max_items: int = 100) -> list[dict[str, Any]]:
        return self._paginated("/equity/history/transactions", max_items=max_items)

    def _get_list(self, path: str) -> list[dict[str, Any]]:
        payload = self._get_json(path, expected_type=list)
        if not all(isinstance(item, dict) for item in payload):
            raise APIError("Trading 212 API 列表项目格式无效。")
        return payload

    def _paginated(self, path: str, *, max_items: int) -> list[dict[str, Any]]:
        if max_items <= 0:
            return []

        page_size = min(50, max_items)
        next_path: str | None = f"{path}?{urlencode({'limit': page_size})}"
        seen: set[str] = set()
        items: list[dict[str, Any]] = []

        while next_path and len(items) < max_items:
            if next_path in seen:
                raise APIError("Trading 212 API 返回了重复的分页游标。")
            seen.add(next_path)

            page = self._get_json(next_path, expected_type=dict)
            page_items = page.get("items")
            if not isinstance(page_items, list):
                raise APIError("Trading 212 API 返回了无效的分页数据。")
            if not all(isinstance(item, dict) for item in page_items):
                raise APIError("Trading 212 API 分页项目格式无效。")

            items.extend(page_items[: max_items - len(items)])
            raw_next = page.get("nextPagePath")
            if raw_next is not None and not isinstance(raw_next, str):
                raise APIError("Trading 212 API 返回了无效的下一页地址。")
            next_path = self._validated_next_path(raw_next) if raw_next else None

        return items

    @staticmethod
    def _validated_next_path(next_page_path: str) -> str:
        absolute = urljoin(f"{LIVE_BASE_URL}/", next_page_path)
        parsed = urlparse(absolute)
        base = urlparse(LIVE_BASE_URL)
        if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
            raise APIError("Trading 212 API 返回了不受信任的下一页地址。")

        prefix = base.path.rstrip("/")
        if not parsed.path.startswith(f"{prefix}/"):
            raise APIError("Trading 212 API 返回了无效的下一页路径。")
        relative_path = parsed.path[len(prefix) :]
        if relative_path not in ALLOWED_PATHS:
            raise APIError("Trading 212 API 返回了不允许的下一页路径。")

        # Re-encode the parsed query to avoid carrying fragments or user-info.
        query = urlencode(parse_qsl(parsed.query, keep_blank_values=True))
        return f"{relative_path}?{query}" if query else relative_path

    def _get_json(self, path: str, *, expected_type: type) -> Any:
        endpoint = path.split("?", 1)[0]
        if endpoint not in ALLOWED_PATHS:
            raise APIError("拒绝访问未列入只读允许列表的 API 路径。")

        url = f"{LIVE_BASE_URL}{path}"
        request = Request(
            url,
            headers={
                "Authorization": self._authorization,
                "Accept": "application/json",
                "User-Agent": "trading212-portfolio-sync/0.1",
            },
            method="GET",
        )

        for attempt in range(self._max_retries + 1):
            try:
                with self._opener(request, timeout=self._timeout) as response:
                    payload = json.load(response)
                if not isinstance(payload, expected_type):
                    raise APIError("Trading 212 API 返回了意外的数据格式。")
                return payload
            except HTTPError as exc:
                if exc.code == 429 and attempt < self._max_retries:
                    self._sleep(self._retry_delay(exc.headers))
                    continue
                raise APIError(
                    f"Trading 212 API 请求失败（HTTP {exc.code}）。",
                    status=exc.code,
                ) from None
            except (URLError, TimeoutError, OSError):
                raise APIError("无法安全连接到 Trading 212 API。") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise APIError("Trading 212 API 返回了无效的 JSON。") from None

        raise APIError("Trading 212 API 请求重试失败。")

    @staticmethod
    def _retry_delay(headers: Any) -> float:
        retry_after = headers.get("Retry-After") if headers else None
        if retry_after:
            try:
                return min(max(float(retry_after), 1.0), 60.0)
            except ValueError:
                pass

        reset = headers.get("x-ratelimit-reset") if headers else None
        if reset:
            try:
                return min(max(float(reset) - time.time(), 1.0), 60.0)
            except ValueError:
                pass
        return 5.0
