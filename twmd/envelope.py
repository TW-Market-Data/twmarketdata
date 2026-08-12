"""Normalise the several response envelope shapes the API returns.

Probing all 82 routes without a key on 2026-08-12 turned up at least four
envelope shapes and three different keys holding the row array::

    {"dataset": ..., "rows": [...],  "count": n, "data_as_of": ..., "lineage": {...}}
    {"dataset": ..., "rows": [...],  "count": n}
    {"dataset_id": ..., "items": [...], "row_count": n, "held_policy": ...}
    {"dataset_id": ..., "data": [...],  "data_count": n, "known_gaps": [...],
     "warnings": [...], "quality": {...}, "request_context": {...}}

So the row key is probed in order rather than hardcoded, and every optional
field is genuinely optional. When a response does not carry lineage or gaps, we
record that we do not know -- we do not synthesise a plausible-looking value.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .meta import Gap

__all__ = ["ROW_KEYS", "extract_rows", "extract_count", "extract_gaps",
           "extract_provenance", "extract_error"]

ROW_KEYS: Tuple[str, ...] = ("rows", "items", "data", "results", "records")
_COUNT_KEYS: Tuple[str, ...] = ("count", "row_count", "data_count", "total")
_GAP_KEYS: Tuple[str, ...] = ("data_gaps", "known_gaps", "gaps")

#: Wrapper keys worth looking inside when the top level holds no rows. Kept
#: deliberately short: metadata blocks in these envelopes contain their own
#: lists -- ``request_context.snapshot_dates_in_page``, ``quality.indices_present``,
#: ``lineage.source_families`` were all observed on 2026-08-12 -- and a
#: "descend and take the first list" rule would return those as if they were
#: data. Returning garbage rows is worse than returning none.
_CONTAINER_KEYS: Tuple[str, ...] = ("envelope", "payload", "body", "response", "result")

#: Never descended into, whatever they contain.
_METADATA_KEYS = frozenset({"lineage", "quality", "request_context", "meta",
                            "error", "warnings", "known_gaps", "data_gaps",
                            "held_policy"})


def extract_rows(payload: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return ``(rows, row_key)``. ``row_key`` is None when no array was found.

    Tries the canonical row keys at the top level first, then looks one level
    inside a short list of wrapper keys, so a nested ``envelope.data`` shape is
    found instead of silently yielding an empty frame. Nested hits are reported
    with their path, e.g. ``"envelope.data"``.
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)], None
    if not isinstance(payload, Mapping):
        return [], None

    for key in ROW_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)], key

    for container in _CONTAINER_KEYS:
        if container in _METADATA_KEYS:
            continue
        inner = payload.get(container)
        if not isinstance(inner, Mapping):
            continue
        for key in ROW_KEYS:
            value = inner.get(key)
            # Rows are objects. Requiring that keeps a list of scalars -- a
            # scope list, a set of dates -- from being mistaken for records.
            if isinstance(value, list) and all(isinstance(r, dict) for r in value):
                return list(value), "%s.%s" % (container, key)
    return [], None


def extract_count(payload: Any, fallback: int) -> int:
    if isinstance(payload, Mapping):
        for key in _COUNT_KEYS:
            value = payload.get(key)
            if isinstance(value, int):
                return value
    return fallback


def extract_gaps(payload: Any) -> Optional[List[Gap]]:
    """Server-declared gaps, or None when the response says nothing about gaps.

    None and ``[]`` mean different things here: None is "the server did not
    tell us", ``[]`` is "the server told us there are none".
    """
    if not isinstance(payload, Mapping):
        return None
    for key in _GAP_KEYS:
        if key not in payload:
            continue
        value = payload[key]
        if value is None:
            return None
        gaps: List[Gap] = []
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if isinstance(item, Mapping):
                    gaps.append(Gap(
                        start=_str_or_none(item.get("start") or item.get("from")
                                           or item.get("start_date")),
                        end=_str_or_none(item.get("end") or item.get("to")
                                         or item.get("end_date")),
                        reason=str(item.get("reason") or item.get("type")
                                   or "declared_by_server"),
                        detail=_str_or_none(item.get("detail") or item.get("note")
                                            or item.get("message")),
                    ))
                elif item is not None:
                    gaps.append(Gap(start=None, end=None, reason="declared_by_server",
                                    detail=str(item)))
        return gaps
    return None


def extract_provenance(payload: Any) -> Dict[str, Any]:
    """Pull whatever provenance the response happens to carry."""
    out: Dict[str, Any] = {
        "data_as_of": None, "source_role": None, "lineage": None, "warnings": [],
    }
    if not isinstance(payload, Mapping):
        return out

    out["data_as_of"] = _str_or_none(payload.get("data_as_of"))
    out["source_role"] = _str_or_none(payload.get("source_role"))
    lineage = payload.get("lineage")
    if isinstance(lineage, Mapping):
        out["lineage"] = dict(lineage)

    warnings = payload.get("warnings")
    if isinstance(warnings, Sequence) and not isinstance(warnings, (str, bytes)):
        out["warnings"] = [str(w) for w in warnings if w is not None]
    elif isinstance(warnings, str):
        out["warnings"] = [warnings]

    # Some envelopes nest freshness inside `meta`.
    meta = payload.get("meta")
    if isinstance(meta, Mapping) and not out["data_as_of"]:
        out["data_as_of"] = _str_or_none(meta.get("last_trading_day")
                                         or meta.get("data_as_of"))
    return out


def extract_error(payload: Any, status_code: int) -> Tuple[Optional[str], str]:
    """Return ``(error_code, message)`` from either error envelope shape.

    ``api.twmarketdata.com`` sends the flat form ``{"error": "code", "message": ...}``
    while the retired gateway sends ``{"error": {"code": ..., "message": ...}}``.
    Both are parsed so the server's own wording survives instead of being
    replaced by a generic "request failed" string.
    """
    code: Optional[str] = None
    message: Optional[str] = None

    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, str):
            code = error
        elif isinstance(error, Mapping):
            raw_code = error.get("code")
            raw_msg = error.get("message")
            code = raw_code if isinstance(raw_code, str) else None
            message = raw_msg if isinstance(raw_msg, str) else None
        for key in ("message", "detail"):
            if message:
                break
            value = payload.get(key)
            if isinstance(value, str):
                message = value

    if not message:
        message = "Request failed with status %d." % status_code
        if code:
            message = "%s (%s)" % (message, code)
    return code, message


def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
