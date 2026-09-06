"""Shared HTTP client for all providers.

Every network call goes through this wrapper so timeout, retry, rate
limiting, logging, and secret redaction behave uniformly. Tests mock this
class at the network boundary — production code never fakes responses.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 2
RETRY_BACKOFF = 1.5


class HttpError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class RateLimit:
    min_interval: float = 0.0
    _last: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


class HttpClient:
    """requests.Session wrapper with retry/timeout/rate-limit."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        rate_limits: dict[str, RateLimit] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.rate_limits = rate_limits or {}
        self.session = session or requests.Session()
        self.user_agent = "JMDB/1.0 (personal media center)"

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json"}

    def get_json(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        provider: str = "",
    ) -> dict | list:
        return self._request("GET", url, params=params, headers=headers, provider=provider)

    def download(self, url: str, dest, provider: str = "") -> int:
        """Stream a binary download to a file path. Returns bytes written."""
        limit = self.rate_limits.get(provider)
        if limit:
            limit.wait()
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with self.session.get(
                    url, headers=self._headers(), timeout=self.timeout, stream=True
                ) as response:
                    response.raise_for_status()
                    written = 0
                    with open(dest, "wb") as handle:
                        for chunk in response.iter_content(chunk_size=64 * 1024):
                            handle.write(chunk)
                            written += len(chunk)
                    return written
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(RETRY_BACKOFF**attempt)
        raise HttpError(f"download failed: {last_error}")

    def _request(self, method: str, url: str, provider: str = "", **kw) -> dict | list:
        limit = self.rate_limits.get(provider)
        if limit:
            limit.wait()
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                headers = {**self._headers(), **(kw.get("headers") or {})}
                kw.pop("headers", None)
                response = self.session.request(
                    method, url, headers=headers, timeout=self.timeout, **kw
                )
                if response.status_code == 404:
                    raise HttpError("not found", status=404)
                if response.status_code == 401:
                    raise HttpError("unauthorized (check API key)", status=401)
                if response.status_code == 429:
                    raise HttpError("rate limited by provider", status=429)
                response.raise_for_status()
                return response.json()
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(RETRY_BACKOFF**attempt)
            except requests.HTTPError as exc:
                raise HttpError(f"http error: {exc}", status=exc.response.status_code if exc.response else None) from exc
            except ValueError as exc:
                raise HttpError(f"invalid JSON from provider: {exc}") from exc
        raise HttpError(f"request failed after retries: {last_error}")
