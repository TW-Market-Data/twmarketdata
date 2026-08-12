"""Data-gap reporting.

Three sources, always labelled, never blended:

``server``          22 of 82 routes take ``include_data_gaps``; we pass it and
                    report what comes back.
``client_derived``  for daily per-entity datasets we can compare the returned
                    dates against ``trading_calendar`` and name the missing
                    sessions. Opt-in, because it costs an extra request.
``unsupported``     the route cannot tell us and we cannot derive it.
``unknown``         the response simply said nothing about gaps.

What this module never does is fill anything in. No zeros, no forward-fill, no
interpolation. A gap is reported as a gap.

Client-derived gaps also cannot distinguish "the source never published this"
from "this table has not loaded it yet" -- only the server knows that -- so
derived gaps carry ``reason="no_row_for_trading_day"`` and nothing stronger.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from .meta import Gap

__all__ = ["DATE_COLUMN_CANDIDATES", "derive_gaps", "pick_date_column"]

DATE_COLUMN_CANDIDATES = (
    "trade_date", "date", "rate_date", "report_date", "as_of_date",
    "settlement_date", "event_date",
)


def pick_date_column(rows: Sequence[Mapping[str, Any]]) -> Optional[str]:
    """Find the daily date column in a response, if there is one."""
    if not rows:
        return None
    first = rows[0]
    for candidate in DATE_COLUMN_CANDIDATES:
        if candidate in first and first[candidate] is not None:
            return candidate
    return None


def derive_gaps(
    rows: Sequence[Mapping[str, Any]],
    trading_days: Iterable[str],
    *,
    date_column: Optional[str] = None,
) -> List[Gap]:
    """Compare returned dates against expected trading days; collapse into runs.

    ``trading_days`` should already be limited to the queried window -- gaps are
    only claimed inside the range actually returned, never past its edges, so a
    short query is not reported as a long outage.
    """
    column = date_column or pick_date_column(rows)
    if not column:
        return []

    present: Set[str] = {
        str(r[column])[:10] for r in rows if r.get(column) is not None
    }
    if not present:
        return []

    lo, hi = min(present), max(present)
    expected = sorted({str(d)[:10] for d in trading_days if lo <= str(d)[:10] <= hi})
    missing = [d for d in expected if d not in present]
    if not missing:
        return []

    gaps: List[Gap] = []
    run_start = run_end = missing[0]
    for day in missing[1:]:
        if _is_next(expected, run_end, day):
            run_end = day
            continue
        gaps.append(_gap(run_start, run_end))
        run_start = run_end = day
    gaps.append(_gap(run_start, run_end))
    return gaps


def _gap(start: str, end: str) -> Gap:
    return Gap(
        start=start,
        end=end,
        reason="no_row_for_trading_day",
        detail=("Derived by comparing returned dates against trading_calendar. "
                "This cannot tell whether the source never published or the table "
                "has not loaded it; only the server can distinguish those."),
    )


def _is_next(expected: List[str], current: str, candidate: str) -> bool:
    try:
        return expected[expected.index(current) + 1] == candidate
    except (ValueError, IndexError):
        return False


def summarise(gaps: Sequence[Gap], source: str) -> Dict[str, Any]:
    """Compact form for logging or JSON output."""
    return {
        "source": source,
        "count": len(gaps),
        "spans": [{"start": g.start, "end": g.end, "reason": g.reason} for g in gaps],
    }
