"""Point-in-time resolution.

Five modes, decided per dataset by the registry and then re-checked against what
the response actually contains:

``server``            the route takes ``as_of``; pass it through.
``client``            PIT-safe and the knowledge column is published; filter locally.
``client_unsafe``     a knowledge column is declared but the dataset is flagged
                      ``point_in_time_safe=false``, meaning that column is a
                      period / effective date / observation date rather than a
                      disclosure date. Filtering on it would reintroduce exactly
                      the look-ahead ``as_of`` exists to prevent, so it is
                      refused unless the caller passes
                      ``as_of_policy="declared_field"``.
``client_unverified`` a knowledge column is declared but does not appear in the
                      published schema; verified against the returned rows at
                      runtime.
``unsupported``       no knowledge axis at all; refused.

Two things override the static mode at runtime:

* If rows carry a server-supplied ``knowledge_date`` (the API is adding this,
  per WORKORDER_API_expose_knowledge_date), that column wins -- it is a real
  knowledge axis and it makes otherwise-unsafe datasets filterable.
* ``kd_imputed=true`` on those rows means the date was derived from a statutory
  filing deadline, not observed from an announcement. Production measurement put
  this at 99.4% of monthly-revenue rows (``kd_source='statutory_deadline'``).
  The SDK filters, but warns, and records the count in ``Meta``. An imputed
  knowledge date is a rule, not a fact, and is never presented as observed.
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .errors import PointInTimeUnavailable
from .meta import (ImputedKnowledgeDateWarning, Meta, PITDataMissingWarning,
                   TruncatedPointInTimeWarning)
from .registry import DatasetInfo

__all__ = ["KNOWLEDGE_DATE_FIELD", "KD_IMPUTED_FIELD", "KD_SOURCE_FIELD",
           "resolve_mode", "apply_as_of", "scan_knowledge_dates"]

KNOWLEDGE_DATE_FIELD = "knowledge_date"
KD_IMPUTED_FIELD = "kd_imputed"
KD_SOURCE_FIELD = "kd_source"

_OPT_IN = "declared_field"


def resolve_mode(info: DatasetInfo, as_of_policy: Optional[str]) -> str:
    """Decide, before the request, how ``as_of`` will be handled.

    Raises when the dataset cannot honour ``as_of`` at all, so the caller finds
    out before spending a request rather than after receiving a frame that looks
    like a replay.
    """
    mode = info.as_of_mode
    if mode == "unsupported":
        raise PointInTimeUnavailable(
            info.key,
            info.as_of_note or "this dataset declares no knowledge-time axis, so there "
                               "is no honest way to replay it to a past date",
        )
    if mode == "client_unsafe" and as_of_policy != _OPT_IN:
        raise PointInTimeUnavailable(
            info.key,
            "%s Query without as_of and align on the disclosure date yourself, or pass "
            "as_of_policy=%r to filter on the declared field anyway and accept the "
            "look-ahead risk. If the API now returns a knowledge_date column for this "
            "dataset, that column is used automatically and this restriction lifts."
            % (info.as_of_note or "point_in_time_safe=false.", _OPT_IN),
        )
    return mode


def scan_knowledge_dates(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Report on server-supplied knowledge_date / kd_imputed / kd_source columns."""
    present = any(KNOWLEDGE_DATE_FIELD in r for r in rows)
    if not present:
        return {"present": False, "non_null": 0, "imputed": None, "sources": []}

    non_null = sum(1 for r in rows if r.get(KNOWLEDGE_DATE_FIELD) is not None)
    has_flag = any(KD_IMPUTED_FIELD in r for r in rows)
    imputed = sum(1 for r in rows if _truthy(r.get(KD_IMPUTED_FIELD))) if has_flag else None
    sources = sorted({str(r[KD_SOURCE_FIELD]) for r in rows
                      if r.get(KD_SOURCE_FIELD) is not None})
    return {"present": True, "non_null": non_null, "imputed": imputed, "sources": sources}


def apply_as_of(
    rows: List[Dict[str, Any]],
    *,
    info: DatasetInfo,
    as_of: str,
    mode: str,
    meta: Meta,
    truncated: bool,
) -> List[Dict[str, Any]]:
    """Filter rows to what was knowable on ``as_of``. Returns the kept rows.

    Only called for the client-side modes; ``server`` mode never reaches here.
    """
    kd = scan_knowledge_dates(rows)
    meta.knowledge_date_present = kd["present"]
    meta.knowledge_date_imputed_rows = kd["imputed"]
    meta.knowledge_date_sources = list(kd["sources"])

    # A server-supplied knowledge_date is a real knowledge axis and outranks the
    # declared field, including on datasets the registry marked unsafe.
    if kd["present"] and kd["non_null"] > 0:
        field = KNOWLEDGE_DATE_FIELD
        if kd["imputed"]:
            pct = 100.0 * kd["imputed"] / max(len(rows), 1)
            note = (
                "%d of %d rows (%.1f%%) carry kd_imputed=true%s: the knowledge date was "
                "derived from a statutory filing deadline, not observed from an "
                "announcement. Treat this as a rule-based approximation of what was "
                "knowable, not as an observed disclosure timestamp."
                % (kd["imputed"], len(rows), pct,
                   " (kd_source=%s)" % ", ".join(kd["sources"]) if kd["sources"] else "")
            )
            warnings.warn(note, ImputedKnowledgeDateWarning, stacklevel=3)
            meta.warnings.append(note)
    else:
        field = info.knowledge_time_field or ""
        if not field:
            note = ("as_of was requested but this response carries no knowledge column, "
                    "so no filter was applied.")
            warnings.warn(note, PITDataMissingWarning, stacklevel=3)
            meta.warnings.append(note)
            meta.as_of_applied = False
            return rows

        usable = sum(1 for r in rows if r.get(field) is not None)
        if rows and usable == 0:
            note = (
                "as_of was requested but %r is null in every returned row of %s, so no "
                "filter was applied and these rows are NOT a point-in-time view. "
                "(Measured on monthly_revenue: announcement_date and "
                "source_publish_date are null in production.)" % (field, info.key)
            )
            warnings.warn(note, PITDataMissingWarning, stacklevel=3)
            meta.warnings.append(note)
            meta.as_of_applied = False
            meta.as_of_field = field
            return rows
        if kd["present"] and kd["non_null"] == 0:
            note = ("knowledge_date is present but null in every row; fell back to %r."
                    % field)
            warnings.warn(note, PITDataMissingWarning, stacklevel=3)
            meta.warnings.append(note)

    kept = [r for r in rows if _le(_as_text(r.get(field)), as_of)]

    meta.as_of_applied = True
    meta.as_of_field = field
    meta.as_of_mode = mode

    if truncated:
        note = (
            "as_of was applied locally to a response that hit the row limit, and this "
            "route has no offset parameter. Rows outside the fetched window are unknown, "
            "so an empty or short result here does not prove nothing was known as of %s."
            % as_of
        )
        warnings.warn(note, TruncatedPointInTimeWarning, stacklevel=3)
        meta.warnings.append(note)

    return kept


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "t", "1", "yes"}
    return bool(value)


def _as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _le(value: Optional[str], as_of: str) -> bool:
    """Lexicographic compare, valid for the ISO-ish forms the API returns.

    Handles ``2026-06``/``2026-06-30``/``2026-06-30T09:00:00Z`` by comparing on
    the shorter of the two prefixes, so a month-grained column is not silently
    excluded by a day-grained cutoff.
    """
    if value is None:
        return False
    n = min(len(value), len(as_of))
    return value[:n] <= as_of[:n]
