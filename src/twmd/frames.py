"""Convert API response envelopes into pandas DataFrames.

The response envelope observed on 2026-07-21 looks like::

    {
      "dataset": "twse_daily_price",
      "rows": [ {...}, ... ],
      "count": 2,
      "data_as_of": "2026-07-17",
      "source_role": "official_twse",
      "lineage": {"provider": "TWSE", ..., "not_investment_advice": true},
      "meta": {"last_trading_day": "...", "market_status": [...]}
    }

Not every dataset uses that shape. Two envelope variants were observed on
2026-07-21:

``rows`` / ``count``
    Used by ``twse-daily-price``, ``tpex-daily-price``, ``monthly-revenue``.
    Records are flat. ``monthly-revenue`` sends a shorter envelope carrying only
    ``dataset``, ``rows`` and ``count``.
``items`` / ``row_count``
    Used by ``security-master`` and ``market-index``. Records contain *nested*
    objects — ``security_identity``, ``market_identity``, ``index_level`` and so
    on — and the envelope carries extra integrity metadata such as
    ``survivorship_bias_warning``.
``data`` / ``quality.row_count``
    Used by ``delisting`` and ``stock-delisting-lifecycle``. Adds
    ``request_context`` (the filters the server actually applied, plus the
    min/max dates it holds), a ``lineage`` block naming the official source
    family, and a top-level ``error`` slot.

Catalog endpoints under ``/v2/data-catalog/`` name their list after themselves
(``reconciliation``, ``stats``); these are picked up by a generic fallback
rather than an entry per endpoint.

:func:`to_dataframe` accepts both. Nested record fields are left as dict-valued
columns rather than flattened, so what you get back is what the API sent; use
:func:`pandas.json_normalize` on the column if you want it expanded.

Everything outside the record list is preserved on ``DataFrame.attrs`` rather
than discarded — including the API's own ``lineage.not_investment_advice`` flag
and any ``survivorship_bias_warning``, both passed through untouched.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

import pandas as pd

#: Envelope keys known to hold the record list, in precedence order.
RECORD_KEYS: Tuple[str, ...] = ("rows", "items", "data")

#: Envelope keys that may hold the server-reported record count.
COUNT_KEYS: Tuple[str, ...] = ("count", "row_count")

#: Envelope keys that never hold records, so the generic fallback skips them.
_NON_RECORD_KEYS = frozenset({"lineage", "meta", "quality", "request_context", "error"})


def record_key(payload: Mapping[str, Any]) -> Optional[str]:
    """Return which envelope key holds the records, or ``None`` if none does.

    Tries the known keys first, then falls back to the first list-valued key
    that is not known metadata. The fallback covers catalog endpoints that name
    their list after themselves — ``/v2/data-catalog/reconciliation`` returns
    ``reconciliation``, ``/v2/data-catalog/stats`` returns ``stats`` — without
    needing an entry per endpoint.
    """
    for key in RECORD_KEYS:
        if isinstance(payload.get(key), list):
            return key
    for key, value in payload.items():
        if key not in _NON_RECORD_KEYS and isinstance(value, list):
            return key
    return None


def server_count(payload: Mapping[str, Any]) -> Optional[int]:
    """Return the server-reported record count across every envelope variant.

    Checks the top level first, then ``quality.row_count``, where the
    ``data``-shaped envelopes put it.
    """
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


def to_dataframe(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Build a DataFrame from one response envelope.

    Handles both the ``rows``/``count`` and ``items``/``row_count`` variants.
    Records become rows; every other envelope key is copied onto ``df.attrs``
    verbatim, so lineage, freshness and integrity metadata survive.

    Args:
        payload: Decoded JSON response body.

    Returns:
        A DataFrame of the records. Empty (no columns) when the record list is
        empty or absent.
    """
    key = record_key(payload)
    records = payload.get(key) or [] if key else []
    frame = pd.DataFrame(records)
    frame.attrs.update({k: v for k, v in payload.items() if k != key})
    return frame


def concat_frames(frames: "list[pd.DataFrame]") -> pd.DataFrame:
    """Concatenate paginated frames, keeping the first page's metadata.

    Args:
        frames: Frames in page order.

    Returns:
        One DataFrame with a fresh RangeIndex. ``attrs`` is taken from the
        first page, with whichever count key that page used — ``count`` or
        ``row_count`` — replaced by the combined record total.
    """
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
