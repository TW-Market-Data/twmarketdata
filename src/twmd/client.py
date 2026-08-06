"""Synchronous data-access client for the TW Market Data API.

Retrieves published datasets and returns them as pandas DataFrames. This is a
transport layer: it fetches records and hands them over unmodified. It does not
compute, score, rank, or interpret anything.
"""

from __future__ import annotations

import email.utils
import json
import os
from datetime import datetime
import random
import time
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence

import httpx
import pandas as pd

from . import access
from .errors import (
    TwmdAPIError,
    TwmdAuthError,
    TwmdConfigError,
    TwmdRateLimitError,
    TwmdServerError,
    TwmdTransportError,
    error_for_status,
)
from .frames import concat_frames, to_dataframe

DEFAULT_BASE_URL = "https://api.twmarketdata.com"
API_KEY_ENV = "TWMD_API_KEY"
BASE_URL_ENV = "TWMD_BASE_URL"
API_KEY_HEADER = "X-API-Key"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.5
DEFAULT_BACKOFF_MAX = 20.0

#: Statuses worth retrying. 401/402/404/422 are terminal — retrying cannot help.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

#: Query parameter names the API uses for a ticker, in the order it accepts them.
_TICKER_PARAMS = ("symbol", "ticker")

#: Longest wait honoured from a ``Retry-After`` header, in seconds. Beyond this
#: the client gives up rather than retrying earlier than the server allowed.
RETRY_AFTER_MAX = 120.0


def _fingerprint(page: "pd.DataFrame") -> str:
    """Stable identity string for a page's first record.

    Used to detect a server that ignored ``offset`` and re-sent page one.
    Serialised rather than compared as a dict because a partially-null numeric
    column yields ``NaN``, and ``NaN != NaN`` makes two identical rows compare
    unequal — which would silently disable the repeat-page guard and let the
    loop refetch page one up to ``max_pages`` times.
    """
    return json.dumps(page.iloc[0].to_dict(), sort_keys=True, default=str)


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Parse a ``Retry-After`` header into seconds.

    RFC 7231 permits two forms: delta-seconds, and an HTTP-date. Both are
    handled; anything unparseable returns ``None`` so the caller falls back to
    its own backoff.
    """
    if not value:
        return None
    text = value.strip()
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    now = datetime.now(when.tzinfo) if when.tzinfo else datetime.now()
    return max(0.0, (when - now).total_seconds())


class Client:
    """Client for the TW Market Data read API.

    Credentials are read from the ``TWMD_API_KEY`` environment variable by
    default; a key is never written to disk or logged by this client. Requests
    without a key still succeed against the key-free datasets described in
    :mod:`twmd.access`.

    Args:
        api_key: API key. Defaults to ``os.environ["TWMD_API_KEY"]``. When
            neither is set the client runs in key-free mode.
        base_url: API root. Defaults to ``TWMD_BASE_URL`` or
            ``https://api.twmarketdata.com``.
        source: Integration marker attached to every request as a ``source``
            query parameter, so the publisher can attribute traffic to the
            integration that produced it (e.g. ``"ecosys/tradingagents"``). It is
            an ordinary query parameter, does not change the response, and
            carries nothing about the user. A per-call ``source`` passed to
            :meth:`get_dataset` overrides it. Leave unset to send nothing.
        timeout: Per-request timeout in seconds.
        max_retries: Retry attempts for transient failures (429, 5xx, network
            errors). Terminal statuses are never retried.
        backoff_factor: Base for exponential backoff, in seconds.
        transport: Optional httpx transport, for tests.

    Example:
        Key-free, zero configuration::

            from twmd import Client

            client = Client()
            df = client.get_dataset("twse-daily-price", symbol="2330", limit=5)
            print(df[["date", "close"]])
            print(df.attrs["lineage"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        source: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if max_retries < 0:
            raise TwmdConfigError("max_retries must be >= 0")
        self._api_key = api_key if api_key is not None else os.environ.get(API_KEY_ENV)
        if self._api_key is not None:
            self._api_key = self._api_key.strip() or None
        self.base_url = (base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")
        self.source = (source or "").strip() or None
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        headers = {"Accept": "application/json", "User-Agent": "twmd-python/0.1.0"}
        if self._api_key:
            headers[API_KEY_HEADER] = self._api_key
        self._http = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )

    # -- lifecycle ---------------------------------------------------------

    @property
    def has_api_key(self) -> bool:
        """Whether this client is carrying a key. Never exposes the key itself."""
        return self._api_key is not None

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # -- public API --------------------------------------------------------

    def get_dataset(
        self,
        dataset: str,
        *,
        as_of: Optional[str] = None,
        **params: Any,
    ) -> pd.DataFrame:
        """Fetch one page of a dataset as a DataFrame.

        Args:
            dataset: Dataset path segment, e.g. ``"twse-daily-price"``. A full
                path such as ``"/v2/datasets/twse-daily-price"`` also works.
            as_of: Point-in-time parameter, forwarded as the ``as_of`` query
                parameter. **Scope is narrow — read this before relying on it.**
                As of the contract probe on 2026-07-21, ``as_of`` is declared on
                exactly four endpoints, all of which require a key:
                ``income-statement``, ``cash-flow-statement``, ``balance-sheet``
                and ``financials``. On every other endpoint it is not a declared
                parameter, and because the API silently ignores unknown query
                parameters — returning 200 rather than 422 — passing it there
                has no observable effect and produces no error. Its behaviour on
                the four declared endpoints has not been verified by this
                client, which has no credentials to exercise them. Treat it as
                forwarded-but-unconfirmed. Note that the ``data_as_of`` field in
                responses is a data-freshness date and is a different thing.
            **params: Query parameters passed through to the API verbatim,
                e.g. ``symbol``, ``limit``, ``date_from``, ``date_to``.

        Returns:
            DataFrame of records. Envelope metadata — ``dataset``, ``count``,
            ``data_as_of``, ``source_role``, ``lineage``, ``meta`` — is on
            ``df.attrs``. The API's own ``lineage.not_investment_advice`` flag
            is preserved as sent.

        Raises:
            TwmdAuthError: 401. Message is annotated with the key-free status of
                this dataset/ticker pair.
            TwmdPaymentRequired: 402 — a valid key whose plan does not include
                the dataset. Full body on ``.body``; ``payment`` fields
                (``price``, ``credits_url``, ``purchase_hint``) also exposed.
            TwmdAPIError: Any other non-2xx response.
            TwmdTransportError: Network failure after retries.
        """
        query = dict(params)
        if as_of is not None:
            query["as_of"] = as_of
        payload = self._request(self._dataset_path(dataset), query)
        return to_dataframe(payload)

    def iter_pages(
        self,
        dataset: str,
        *,
        limit: int = 1000,
        max_pages: int = 100,
        as_of: Optional[str] = None,
        **params: Any,
    ) -> Iterator[pd.DataFrame]:
        """Yield successive pages of a dataset.

        **Pagination is defensive by necessity.** The API publishes no cursor:
        the probe on 2026-07-21 found no ``cursor`` or ``next_cursor`` field in
        any response and none in the OpenAPI document. Paging is expressed as
        ``limit``/``offset``, and ``offset`` was measured to be *ignored* on the
        key-free endpoints — ``offset=3`` returned the same records as
        ``offset=0``. So this method advances ``offset`` as the API documents,
        but guards against it having no effect:

        1. Stop when a page returns fewer records than ``limit`` (the last page).
        2. Stop when a page repeats the previous page's first record, which is
           what a silently-ignored ``offset`` produces. Without this guard the
           loop would refetch page one until ``max_pages``.

        In practice, against endpoints that ignore ``offset``, this yields
        exactly one page. That is the correct outcome, not a failure.

        Args:
            dataset: Dataset path segment.
            limit: Records requested per page.
            max_pages: Hard ceiling on pages fetched, as a runaway guard.
            as_of: See :meth:`get_dataset`.
            **params: Additional query parameters.

        Yields:
            One DataFrame per page.
        """
        offset = 0
        previous_first: Optional[str] = None
        for _ in range(max_pages):
            page = self.get_dataset(dataset, as_of=as_of, limit=limit, offset=offset, **params)
            if page.empty:
                return
            first = _fingerprint(page)
            if previous_first is not None and first == previous_first:
                # offset had no effect; the server re-sent the same page.
                return
            yield page
            if len(page) < limit:
                return
            previous_first = first
            offset += limit

    def get_all(
        self,
        dataset: str,
        *,
        limit: int = 1000,
        max_pages: int = 100,
        as_of: Optional[str] = None,
        **params: Any,
    ) -> pd.DataFrame:
        """Fetch every page and concatenate. See :meth:`iter_pages` for limits."""
        pages = list(
            self.iter_pages(
                dataset, limit=limit, max_pages=max_pages, as_of=as_of, **params
            )
        )
        return concat_frames(pages)

    def list_datasets(self) -> pd.DataFrame:
        """Fetch the dataset catalog."""
        payload = self._request("/v2/datasets", {})
        return to_dataframe(payload)

    def find_related(
        self,
        *,
        as_of: str,
        ticker: Optional[str] = None,
        dataset_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Traverse the knowledge graph: value-chain peers for a ticker, or join-able
        datasets for a dataset id.

        Returns the raw payload rather than a DataFrame because the two answers have
        different shapes — ``value_chain_nodes``/``peers_in_node`` for a ticker,
        ``dataset_relations`` for a dataset id — and flattening either into one table
        would lose the distinction. The keys match the MCP ``find_related`` tool, so the
        same handling works against both surfaces.

        Args:
            as_of: Point-in-time date, ``YYYY-MM-DD``. **Required by the API**, and
                unlike the narrow ``as_of`` on :meth:`get_dataset` this one is genuinely
                enforced: industry-chain membership is *captured*, so the endpoint
                answers from the latest capture at or before this date. An ``as_of``
                earlier than the first capture returns empty membership plus a ``note``
                explaining why — that is the look-ahead guard working, not an error.
                The capture actually used is reported at ``meta.chain_capture_date``.
            ticker: e.g. ``"2330"``. Returns its value-chain nodes and the other
                tickers in those nodes.
            dataset_id: e.g. ``"equity_daily_prices"``. Returns declared join targets,
                each with ``to`` / ``on`` / ``why``.
            limit: Max peers per node (server default 50, max 200).

        Returns:
            Payload dict. For a ticker: ``ticker``, ``value_chain_nodes``,
            ``peers_in_node``, optional ``note``, and ``meta``. For a dataset id:
            ``dataset_relations`` and ``meta``.

        Raises:
            ValueError: Neither ``ticker`` nor ``dataset_id`` given — caught here rather
                than spending a round trip to be told the same thing.
            TwmdAuthError: 401. The endpoint requires a key, matching the other /v2
                surfaces; it is not tier-gated.
            TwmdAPIError: 404 for an unknown ``dataset_id``; any other non-2xx.
        """
        if not ticker and not dataset_id:
            raise ValueError("provide ticker or dataset_id")
        return self._request(
            "/v2/find-related",
            {"as_of": as_of, "ticker": ticker, "dataset_id": dataset_id, "limit": limit},
        )

    def is_key_free(self, dataset: str, ticker: Optional[str] = None) -> bool:
        """Whether a dataset/ticker pair is reachable without a key.

        Thin re-export of :func:`twmd.access.is_key_free` so callers can check
        before requesting.
        """
        return access.is_key_free(dataset, ticker)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _dataset_path(dataset: str) -> str:
        name = dataset.strip("/")
        if name.startswith("v2/"):
            return "/" + name
        return "/v2/datasets/" + name

    def _request(self, path: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        """Issue a GET with retry/backoff and map failures onto exceptions."""
        clean = {k: v for k, v in params.items() if v is not None}
        # Attach the integration source marker to every request. An explicit
        # per-call ``source`` wins, so a caller can override it; otherwise the
        # client-wide marker is used. It is an ordinary query parameter the API
        # ignores for data selection (verified: it does not enter the
        # ``request_context.filters`` of data-shaped responses).
        if self.source is not None and "source" not in clean:
            clean["source"] = self.source
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._http.get(path, params=clean)
            except httpx.HTTPError as exc:
                last_exc = TwmdTransportError(f"request to {path} failed: {exc}")
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt, None)
                    continue
                raise last_exc from exc

            if response.status_code < 300:
                return self._decode(response)

            body = self._safe_json(response)
            exc_obj = error_for_status(
                response.status_code,
                body=body,
                text=response.text,
                request_url=str(response.request.url),
            )

            if response.status_code in RETRY_STATUSES and attempt < self.max_retries:
                if self._sleep_before_retry(attempt, response.headers.get("Retry-After")):
                    last_exc = exc_obj
                    continue
                # Server asked us to wait longer than we are willing to.
                raise exc_obj

            if isinstance(exc_obj, TwmdAuthError):
                raise self._annotate_auth_error(exc_obj, path, clean)
            raise exc_obj

        # Retries exhausted on a retryable status.
        assert last_exc is not None
        raise last_exc

    def _decode(self, response: httpx.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise TwmdAPIError(
                response.status_code,
                text=response.text,
                request_url=str(response.request.url),
            ) from exc
        if not isinstance(payload, dict):
            return {"rows": payload if isinstance(payload, list) else [payload]}
        return payload

    @staticmethod
    def _safe_json(response: httpx.Response) -> Optional[Dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else {"detail": payload}

    def _annotate_auth_error(
        self, exc: TwmdAuthError, path: str, params: Mapping[str, Any]
    ) -> TwmdAuthError:
        """Append key-free context to a 401 so the cause is obvious."""
        dataset = path.rsplit("/", 1)[-1]
        ticker = next(
            (str(params[p]) for p in _TICKER_PARAMS if params.get(p) is not None), None
        )
        hint = access.explain(dataset, ticker)
        if not self.has_api_key:
            hint += f" No API key is set; export {API_KEY_ENV} to send one."
        exc.args = (f"{exc.args[0]} — {hint}",)
        return exc

    def _sleep_before_retry(self, attempt: int, retry_after: Optional[str]) -> bool:
        """Wait before the next attempt. Returns whether a retry should proceed.

        A ``Retry-After`` header is honoured **exactly** — no jitter, no
        shortening — because retrying sooner than the server permitted is worse
        than waiting too long. If it asks for longer than
        :data:`RETRY_AFTER_MAX`, this returns ``False`` so the caller raises the
        server's own error rather than sleeping for minutes or retrying early.

        Otherwise: exponential backoff with jitter.
        """
        delay = parse_retry_after(retry_after)
        if delay is not None:
            if delay > RETRY_AFTER_MAX:
                return False
            time.sleep(delay)
            return True
        backoff = min(self.backoff_factor * (2 ** attempt), DEFAULT_BACKOFF_MAX)
        time.sleep(backoff * (0.5 + random.random() / 2))
        return True


__all__: Sequence[str] = ["Client"]
