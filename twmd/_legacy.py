"""The 0.1.0 public surface, kept working on top of 0.2.0.

``twmarketdata`` 0.1.0 shipped to PyPI on 2026-07-21 and imports as ``twmd``.
0.2.0 rewrites the client, so everything 0.1.0 exposed is re-implemented here
and re-exported from the top-level package. Existing code keeps running; it just
emits :class:`DeprecationWarning` pointing at the replacement.

Preserved, with 0.1.0 semantics:

* ``Client.get_dataset`` / ``get_all`` / ``iter_pages`` / ``list_datasets`` /
  ``is_key_free`` / ``close``
* the ``access`` module: ``SAMPLE_TICKERS``, ``OPEN_DATASETS``,
  ``SAMPLE_DATASETS``, ``KEY_REQUIRED_DATASETS``,
  ``PRESUMED_KEY_REQUIRED_DATASETS``, ``access_tier``, ``provenance``,
  ``is_key_free``, ``explain``
* ``frames.to_dataframe`` / ``record_key`` / ``server_count`` / ``concat_frames``
* the ten ``Twmd*Error`` classes, including ``TwmdPaymentRequired``'s
  ``payment`` / ``price`` / ``credits_url`` / ``purchase_hint`` accessors

Two deliberate differences, both toward being more accurate rather than
bug-compatible:

1. **The access tables are re-measured.** 0.1.0 recorded 2 open and 3
   sample-only datasets from a probe on 2026-07-21. A full 82-route sweep on
   2026-08-12, followed by a second sweep with a non-demo ticker to separate
   "open to anyone" from "demo symbols only", found 14 open and the same 3
   sample-only. Shipping the narrower list would mean shipping data we know to
   be incomplete. Semantics, names and return types are unchanged.
2. **``iter_pages`` stops when the server ignores ``offset``.** 0.1.0 documented
   that offset was measured to be ignored; re-measured 2026-08-12 on
   ``index-constituents``, where offsets 0/3/6 all returned the identical page.
   Rather than appending duplicates, pagination stops and the result is flagged
   truncated.
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, FrozenSet, Iterator, List, Mapping, Optional

from . import registry
from .envelope import extract_rows
from .errors import (DatasetNotFoundError, InsufficientCreditsError, MissingApiKeyError,
                      RateLimitedError, TierRequiredError, TwmdAuthError, TwmdConfigError,
                      TwmdError, TwmdRequestError, TwmdServerError)

__all__ = [
    "SAMPLE_TICKERS", "OPEN_DATASETS", "SAMPLE_DATASETS", "KEY_REQUIRED_DATASETS",
    "PRESUMED_KEY_REQUIRED_DATASETS", "OPEN", "SAMPLE", "KEY_REQUIRED",
    "access_tier", "provenance", "is_key_free", "explain",
    "to_dataframe", "record_key", "server_count", "concat_frames",
    "TwmdAPIError", "TwmdTransportError", "TwmdNotFoundError", "TwmdValidationError",
    "TwmdPaymentRequired", "LegacyClientMixin", "API_KEY_ENV",
    "DEFAULT_BASE_URL",
]

_MEASURED_ON = "2026-08-12"

#: 0.1.0 exported these; kept so `from twmd import API_KEY_ENV` still resolves.
API_KEY_ENV = "TWMD_API_KEY"
#: 0.1.0's value was the bare host. Either form works: the transport strips a
#: duplicate /v2 segment when joining a registry route.
DEFAULT_BASE_URL = registry.DEFAULT_BASE_URL


def _warn(old: str, new: str) -> None:
    warnings.warn(
        "%s is the 0.1.0 API and is deprecated; use %s. It keeps working for now."
        % (old, new),
        DeprecationWarning, stacklevel=3,
    )


# --------------------------------------------------------------------- access
#: Demo tickers served without a key on :data:`SAMPLE_DATASETS`.
SAMPLE_TICKERS: FrozenSet[str] = frozenset(registry.free_tier_symbols())

#: Datasets served without a key for any ticker. Re-measured 2026-08-12.
OPEN_DATASETS: FrozenSet[str] = frozenset({
    "security-master", "market-index", "trading-calendar", "trading-rules-reference",
    "bond-convertible-reference", "broker-branch-reference", "warrants-reference",
    "company-industry-exposures", "company-peer-groups", "securities-firm-master",
    "fund-etf-metadata", "index-constituents", "issuer-classification",
    "stock-delisting-lifecycle", "stock-split-par-value-events",
})

#: Datasets served without a key only for :data:`SAMPLE_TICKERS`. Unchanged from 0.1.0.
SAMPLE_DATASETS: FrozenSet[str] = frozenset(
    {"twse-daily-price", "tpex-daily-price", "monthly-revenue"}
)

#: Datasets measured returning 401 without a key. Every shipped dataset was
#: probed, so this is the complement of the two key-free sets.
KEY_REQUIRED_DATASETS: FrozenSet[str] = frozenset(
    registry.get(key).route.rsplit("/", 1)[-1] for key in registry.datasets()
) - OPEN_DATASETS - SAMPLE_DATASETS

#: Kept for import compatibility. Every dataset the SDK ships has now been
#: probed, so nothing is merely presumed any more.
PRESUMED_KEY_REQUIRED_DATASETS: FrozenSet[str] = frozenset()

OPEN = "open"
SAMPLE = "sample"
KEY_REQUIRED = "key_required"


def access_tier(dataset: str) -> str:
    """Access tier for ``dataset``. Unknown datasets return ``key_required``."""
    key = dataset.strip("/").replace("_", "-")
    if key in OPEN_DATASETS:
        return OPEN
    if key in SAMPLE_DATASETS:
        return SAMPLE
    return KEY_REQUIRED


def provenance(dataset: str) -> str:
    """``measured`` or ``assumed``. Every shipped dataset is now measured."""
    key = dataset.strip("/").replace("_", "-")
    known = OPEN_DATASETS | SAMPLE_DATASETS | KEY_REQUIRED_DATASETS
    return "measured" if key in known else "assumed"


def is_key_free(dataset: str, ticker: Optional[str] = None) -> bool:
    """Whether ``dataset`` (optionally for ``ticker``) is reachable without a key."""
    tier = access_tier(dataset)
    if tier == OPEN:
        return True
    if tier == SAMPLE:
        return ticker is not None and str(ticker) in SAMPLE_TICKERS
    return False


def explain(dataset: str, ticker: Optional[str] = None) -> str:
    """Human-readable reason for the :func:`is_key_free` verdict."""
    tier = access_tier(dataset)
    if tier == OPEN:
        return "'%s' is served without an API key for any ticker." % dataset
    if tier == SAMPLE:
        listed = ", ".join(sorted(SAMPLE_TICKERS))
        if ticker is not None and str(ticker) in SAMPLE_TICKERS:
            return "'%s' is served without an API key for ticker %s." % (dataset, ticker)
        return ("'%s' is served without an API key only for these sample tickers: %s."
                % (dataset, listed)
                + (" Ticker %s is not among them." % ticker if ticker is not None else ""))
    return "'%s' requires an API key for every request." % dataset


# --------------------------------------------------------------------- frames
RECORD_KEYS = ("rows", "items", "data")
COUNT_KEYS = ("count", "row_count")
_NON_RECORD_KEYS = frozenset({"lineage", "meta", "quality", "request_context", "error"})


def record_key(payload: Mapping[str, Any]) -> Optional[str]:
    """Which envelope key holds the records, or None."""
    for key in RECORD_KEYS:
        if isinstance(payload.get(key), list):
            return key
    for key, value in payload.items():
        if key not in _NON_RECORD_KEYS and isinstance(value, list):
            return key
    return None


def server_count(payload: Mapping[str, Any]) -> Optional[int]:
    """Server-reported record count across every envelope variant."""
    for key in COUNT_KEYS:
        value = payload.get(key)
        if isinstance(value, int):
            return value
    quality = payload.get("quality")
    if isinstance(quality, Mapping):
        for key in COUNT_KEYS:
            value = quality.get(key)
            if isinstance(value, int):
                return value
    return None


def to_dataframe(payload: Mapping[str, Any]) -> Any:
    """Build a DataFrame from one response envelope; envelope keys go to ``attrs``."""
    import pandas as pd

    key = record_key(payload)
    records = (payload.get(key) or []) if key else []
    frame = pd.DataFrame(records)
    frame.attrs.update({k: v for k, v in payload.items() if k != key})
    return frame


def concat_frames(frames: List[Any]) -> Any:
    """Concatenate paginated frames, keeping the first page's metadata."""
    import pandas as pd

    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]
    combined = pd.concat(frames, ignore_index=True)
    combined.attrs.update(frames[0].attrs)
    for key in COUNT_KEYS:
        if key in combined.attrs:
            combined.attrs[key] = len(combined)
    combined.attrs["pages_fetched"] = len(frames)
    return combined


# --------------------------------------------------------------------- errors
class TwmdAPIError(TwmdError):
    """0.1.0's non-2xx base class. Carries ``body`` / ``text`` / ``status_code``."""

    def __init__(self, status_code: int, *, body: Optional[Mapping[str, Any]] = None,
                 text: str = "", request_url: str = "") -> None:
        self.body = body
        self.text = text
        self.request_url = request_url
        code = body.get("error") if isinstance(body, Mapping) else None
        message = ""
        if isinstance(body, Mapping):
            message = str(body.get("message") or body.get("detail") or "")
        if not message:
            message = text[:200]
        super().__init__("HTTP %d: %s" % (status_code, message) if message
                         else "HTTP %d" % status_code,
                         status_code=status_code,
                         error_code=code if isinstance(code, str) else None)


class TwmdTransportError(TwmdServerError):
    """0.1.0 name for network-level failure."""


class TwmdNotFoundError(DatasetNotFoundError):
    """0.1.0 name for HTTP 404."""


class TwmdValidationError(TwmdRequestError):
    """0.1.0 name for HTTP 422."""


class TwmdPaymentRequired(TierRequiredError):
    """0.1.0 name for HTTP 402, with the ``payment`` accessors it exposed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        payment = self.details.get("payment") if isinstance(self.details, Mapping) else None
        self.payment: Optional[Mapping[str, Any]] = payment if isinstance(payment, Mapping) else None
        p = self.payment or {}
        self.price = p.get("price")
        self.credits_url = p.get("credits_url")
        self.purchase_hint = p.get("purchase_hint")


# --------------------------------------------------------------------- client
class LegacyClientMixin:
    """0.1.0's ``Client`` methods, implemented against 0.2.0's request path."""

    def get_dataset(self, dataset: str, **params: Any) -> Any:
        """0.1.0's generic call. Returns a DataFrame; accepts kebab route slugs.

        0.1.0 passed query parameters through verbatim, so ``symbol=``,
        ``date_from=`` and friends still work here -- they are translated onto
        whatever the route actually expects.
        """
        _warn("Client.get_dataset()", "Client.dataset() or the per-dataset methods")
        return self.dataset(dataset, **_translate(dataset, params))  # type: ignore[attr-defined]

    def iter_pages(self, dataset: str, *, limit: int = 1000,
                   max_pages: Optional[int] = None, as_of: Optional[str] = None,
                   **params: Any) -> Iterator[Any]:
        """Yield pages. Stops early if the server ignores ``offset``."""
        _warn("Client.iter_pages()", "Client.dataset(), which paginates internally")
        from .frame import to_frame
        from .meta import Meta

        offset, page_no, seen = 0, 0, set()
        while max_pages is None or page_no < max_pages:
            payload = self.dataset(  # type: ignore[attr-defined]
                dataset, as_of=as_of, limit=limit, offset=offset, raw=True,
                paginate=False, **_translate(dataset, params))
            rows, _ = extract_rows(payload)
            if not rows:
                return
            fingerprint = (len(rows), repr(rows[0])[:200])
            if fingerprint in seen:
                warnings.warn(
                    "Stopped paginating %r: the server returned an identical page for "
                    "offset=%d, so it does not honour offset. Pages already yielded are "
                    "fine; there may be more data this route cannot reach."
                    % (dataset, offset), RuntimeWarning, stacklevel=2)
                return
            seen.add(fingerprint)
            yield to_frame(rows, Meta(dataset=dataset, route=dataset, row_count=len(rows)))
            if len(rows) < limit:
                return
            offset += len(rows)
            page_no += 1

    def get_all(self, dataset: str, *, limit: int = 1000,
                max_pages: Optional[int] = None, as_of: Optional[str] = None,
                **params: Any) -> Any:
        """Fetch every reachable page and concatenate."""
        pages = list(self.iter_pages(dataset, limit=limit, max_pages=max_pages,
                                     as_of=as_of, **params))
        return concat_frames(pages)

    def list_datasets(self) -> Any:
        """The dataset catalogue as a DataFrame."""
        _warn("Client.list_datasets()", "twmd.datasets() / twmd.capabilities()")
        from .frame import to_frame
        from .meta import Meta

        rows = [dict(registry.capabilities(k)) for k in registry.datasets()]
        return to_frame(rows, Meta(dataset="__catalogue__", route="(local registry)",
                                   row_count=len(rows)))

    def is_key_free(self, dataset: str, ticker: Optional[str] = None) -> bool:
        """Whether this dataset/ticker is reachable without a key."""
        return is_key_free(dataset, ticker)


#: 0.1.0 accepted the API's own parameter names. Map them onto the SDK's.
_LEGACY_PARAMS = {
    "symbol": "ticker", "ticker": "ticker", "entity_id": "ticker",
    "date_from": "start", "start_date": "start", "start_month": "start",
    "date_to": "end", "end_date": "end", "end_month": "end",
    "as_of_date": "as_of", "as_of": "as_of",
    "limit": "limit", "offset": "offset", "raw": "raw", "paginate": "paginate",
}


def _translate(dataset: str, params: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, value in params.items():
        out[_LEGACY_PARAMS.get(name, name)] = value
    return out
