"""Which dataset/ticker combinations are reachable without an API key.

This module encodes an **empirically measured** matrix, not an assumption. It
was produced by probing the live API without credentials on 2026-07-21. The
headline finding: key-free access is scoped per *dataset*, not globally per
ticker. The same ticker that returns 200 on ``twse-daily-price`` returns 401 on
``institutional-flow``.

Three access tiers were observed:

``OPEN``
    Reachable without a key for any ticker.
``SAMPLE``
    Reachable without a key only for the five sample tickers in
    :data:`SAMPLE_TICKERS`. Any other ticker returns 401 ``missing_api_key``.
``KEY_REQUIRED``
    Every request needs a key.

Datasets absent from the tables below are treated as ``KEY_REQUIRED``, which is
the safe default: the client will still send the request, so an unlisted
dataset that is in fact open keeps working. This module drives *advisory*
hints, never a client-side block.
"""

from __future__ import annotations

from typing import FrozenSet, Optional

#: Tickers served without a key on :data:`SAMPLE_DATASETS`. Measured 2026-07-21.
SAMPLE_TICKERS: FrozenSet[str] = frozenset({"2330", "2317", "2454", "0050", "2603"})

#: Datasets served without a key for any ticker. Measured 2026-07-21.
OPEN_DATASETS: FrozenSet[str] = frozenset({"security-master", "market-index"})

#: Datasets served without a key only for :data:`SAMPLE_TICKERS`. Measured 2026-07-21.
SAMPLE_DATASETS: FrozenSet[str] = frozenset(
    {"twse-daily-price", "tpex-daily-price", "monthly-revenue"}
)

#: Datasets *measured* returning 401 without a key, including for sample
#: tickers. Each of these was probed directly on 2026-07-21.
KEY_REQUIRED_DATASETS: FrozenSet[str] = frozenset(
    {
        "institutional-flow",
        "technical-indicators",
        "valuation-data",
        "market-prices",
        "financial-metrics",
        "market-snapshot",
        "market-breadth",
        "income-statement",
    }
)

#: Datasets *believed* key-gated but never probed. They declare ``x-api-key`` in
#: the OpenAPI document and sit alongside measured-gated siblings, but no
#: request was issued against them. Kept separate from
#: :data:`KEY_REQUIRED_DATASETS` so the distinction between measured and assumed
#: is not lost. They resolve to the same tier; only the provenance differs.
PRESUMED_KEY_REQUIRED_DATASETS: FrozenSet[str] = frozenset(
    {
        "cash-flow-statement",
        "balance-sheet",
        "financials",
    }
)

OPEN = "open"
SAMPLE = "sample"
KEY_REQUIRED = "key_required"


def access_tier(dataset: str) -> str:
    """Return the access tier for ``dataset``.

    Unknown datasets return :data:`KEY_REQUIRED`, the safe default.
    """
    key = dataset.strip("/")
    if key in OPEN_DATASETS:
        return OPEN
    if key in SAMPLE_DATASETS:
        return SAMPLE
    return KEY_REQUIRED


def provenance(dataset: str) -> str:
    """How the tier for ``dataset`` was established: ``measured`` or ``assumed``.

    Lets a caller — or a future contract re-probe — tell apart what was actually
    observed from what is only the safe default.
    """
    key = dataset.strip("/")
    measured = OPEN_DATASETS | SAMPLE_DATASETS | KEY_REQUIRED_DATASETS
    return "measured" if key in measured else "assumed"


def is_key_free(dataset: str, ticker: Optional[str] = None) -> bool:
    """Whether ``dataset`` (optionally for ``ticker``) is reachable without a key.

    Args:
        dataset: Dataset path segment, e.g. ``"twse-daily-price"``.
        ticker: Symbol to check. Required to get a meaningful answer for
            ``SAMPLE``-tier datasets; without it this returns ``False`` for
            them, since only five specific tickers qualify.

    Returns:
        ``True`` if an unauthenticated request is expected to succeed.

    Example:
        >>> is_key_free("twse-daily-price", "2330")
        True
        >>> is_key_free("twse-daily-price", "1101")
        False
        >>> is_key_free("security-master", "1101")
        True
        >>> is_key_free("institutional-flow", "2330")
        False
    """
    tier = access_tier(dataset)
    if tier == OPEN:
        return True
    if tier == SAMPLE:
        return ticker is not None and str(ticker) in SAMPLE_TICKERS
    return False


def explain(dataset: str, ticker: Optional[str] = None) -> str:
    """Human-readable reason for the :func:`is_key_free` verdict.

    Used to enrich 401 messages so a caller can tell "I forgot my key" apart
    from "this dataset is open but that ticker is not in the sample set".
    """
    tier = access_tier(dataset)
    if tier == OPEN:
        return f"'{dataset}' is served without an API key for any ticker."
    if tier == SAMPLE:
        listed = ", ".join(sorted(SAMPLE_TICKERS))
        if ticker is not None and str(ticker) in SAMPLE_TICKERS:
            return f"'{dataset}' is served without an API key for ticker {ticker}."
        return (
            f"'{dataset}' is served without an API key only for these sample "
            f"tickers: {listed}."
            + (f" Ticker {ticker} is not among them." if ticker is not None else "")
        )
    return f"'{dataset}' requires an API key for every request."
