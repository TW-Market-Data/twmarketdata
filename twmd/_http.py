"""HTTP transport: retries, backoff, and a concurrency ceiling.

The concurrency ceiling is not decoration. Probing all 82 routes at four
concurrent requests tripped ``403 temporarily_blocked``, and the block persisted
for tens of minutes. The response carries no ``Retry-After`` and no quota
information, so a client that hammers on has nothing to go on. Default
concurrency is therefore 2, and 403 temporarily_blocked is retried with backoff
like the rate limit it is, not surfaced as a permissions failure.
"""
from __future__ import annotations

import random
import threading
import time
from typing import Any, Dict, Mapping, Optional, Tuple

import requests

from .envelope import extract_error
from .errors import RateLimitedError, TwmdError, TwmdServerError, classify

__all__ = ["Transport", "Response"]

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_RETRY_CODES = frozenset({
    "temporarily_blocked", "rate_limit_exceeded", "upstream_error", "upstream_timeout",
})


class Response:
    """A successful HTTP response, already JSON-decoded."""

    __slots__ = ("payload", "status_code", "headers", "url")

    def __init__(self, payload: Any, status_code: int,
                 headers: Mapping[str, str], url: str) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers
        self.url = url

    @property
    def request_id(self) -> Optional[str]:
        for key in ("X-Request-Id", "x-request-id", "X-Request-ID"):
            value = self.headers.get(key)
            if value:
                return str(value)
        return None


class Transport:
    """Thin wrapper over ``requests.Session`` with the retry policy applied."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 5,
        max_concurrency: int = 2,
        backoff_base: float = 1.5,
        backoff_cap: float = 60.0,
        user_agent: str = "twmd-python-sdk",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        self._semaphore = threading.BoundedSemaphore(max(1, int(max_concurrency)))
        self._sleep = time.sleep

    # ------------------------------------------------------------------ url
    def url_for(self, route: str) -> str:
        """Join the base URL with a registry route without duplicating ``/v2``.

        Registry routes are absolute (``/v2/datasets/x``) while the default base
        URL already ends in ``/v2``, so a naive concatenation would produce
        ``/v2/v2/datasets/x``.
        """
        path = route if route.startswith("/") else "/" + route
        base = self.base_url
        for segment in ("/v2", "/v1"):
            if base.endswith(segment) and path.startswith(segment + "/"):
                path = path[len(segment):]
                break
        return base + path

    # ------------------------------------------------------------------ get
    def get(self, route: str, params: Mapping[str, Any], *,
            dataset: Optional[str] = None) -> Response:
        url = self.url_for(route)
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        clean = {k: v for k, v in params.items() if v is not None}
        last_error: Optional[TwmdError] = None

        for attempt in range(self.max_retries + 1):
            with self._semaphore:
                try:
                    raw = self._session.get(url, params=clean, headers=headers,
                                            timeout=self.timeout)
                except requests.Timeout as exc:
                    last_error = TwmdServerError(
                        "Request to %s timed out after %ss." % (url, self.timeout),
                        dataset=dataset)
                    if attempt >= self.max_retries:
                        raise last_error from exc
                    self._backoff(attempt, None)
                    continue
                except requests.RequestException as exc:
                    last_error = TwmdServerError(
                        "Request to %s failed: %s" % (url, exc), dataset=dataset)
                    if attempt >= self.max_retries:
                        raise last_error from exc
                    self._backoff(attempt, None)
                    continue

            try:
                payload: Any = raw.json()
            except ValueError:
                payload = {"raw": raw.text}

            if raw.ok:
                return Response(payload, raw.status_code, raw.headers, raw.url)

            code, message = extract_error(payload, raw.status_code)
            retry_after = _retry_after(raw.headers)
            error = classify(
                raw.status_code, code, message,
                request_id=Response(payload, raw.status_code, raw.headers, raw.url).request_id,
                dataset=dataset, retry_after=retry_after,
                details=payload if isinstance(payload, Mapping) else {"raw": payload},
            )

            retryable = raw.status_code in _RETRY_STATUSES or code in _RETRY_CODES
            if retryable and attempt < self.max_retries:
                last_error = error
                self._backoff(attempt, retry_after)
                continue
            raise error

        raise last_error or TwmdServerError("Request failed.", dataset=dataset)

    # -------------------------------------------------------------- backoff
    def _backoff(self, attempt: int, retry_after: Optional[float]) -> None:
        if retry_after is not None:
            delay = retry_after
        else:
            delay = min(self.backoff_base ** (attempt + 1), self.backoff_cap)
            delay *= 0.5 + random.random()  # jitter, so retries do not synchronise
        self._sleep(min(delay, self.backoff_cap))

    def close(self) -> None:
        self._session.close()


def _retry_after(headers: Mapping[str, str]) -> Optional[float]:
    for key in ("Retry-After", "retry-after"):
        value = headers.get(key)
        if not value:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None
