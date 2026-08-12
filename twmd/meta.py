"""Response metadata and the warning types the SDK uses to stay honest.

Every value here is either something the API told us or something we derived and
labelled as derived. Nothing is guessed. Where the API gave us nothing, the
field is ``None`` or the source is ``"unknown"`` -- never an optimistic default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "Gap", "Meta",
    "TwmdWarning", "PITDataMissingWarning", "ImputedKnowledgeDateWarning",
    "TruncatedPointInTimeWarning", "TruncatedResultWarning",
    "CompatSubstitutionWarning", "DatasetStatusWarning",
]


class TwmdWarning(UserWarning):
    """Base class for every warning this SDK emits."""


class PITDataMissingWarning(TwmdWarning):
    """``as_of`` was requested but the knowledge column is absent or entirely null.

    Emitted instead of filtering, because filtering on a column that has no
    values would silently return everything or nothing depending on the
    comparison, and either way it would look like a successful replay.
    """


class ImputedKnowledgeDateWarning(TwmdWarning):
    """Some or all knowledge dates in this response are imputed, not observed.

    ``kd_imputed=true`` means the date was derived from a statutory filing
    deadline (e.g. monthly revenue is due by the 10th of the following month),
    not read from an actual announcement timestamp. A backtest aligned on an
    imputed date is aligned on a rule, not on what the market actually knew.
    """


class TruncatedPointInTimeWarning(TwmdWarning):
    """A client-side ``as_of`` filter ran on a response that hit the row limit.

    The rows dropped by truncation are unknown, so "nothing was known as of that
    date" and "the known rows fell outside the fetched window" are not
    distinguishable here.
    """


class TruncatedResultWarning(TwmdWarning):
    """The response hit ``limit`` on a route with no offset parameter."""


class CompatSubstitutionWarning(TwmdWarning):
    """A compat call was served by a TWMD dataset with different semantics."""


class DatasetStatusWarning(TwmdWarning):
    """The dataset is not ``active`` (partial / planned / private_beta)."""


@dataclass(frozen=True)
class Gap:
    """A stretch of missing data.

    ``reason`` distinguishes cases that must not be conflated: a source that
    never published, a source that publishes no archive so the history is
    permanently unobtainable, and a table that simply has not been loaded yet.
    """

    start: Optional[str]
    end: Optional[str]
    reason: str
    detail: Optional[str] = None

    def __str__(self) -> str:
        span = "%s..%s" % (self.start or "?", self.end or "?")
        return "%s (%s)" % (span, self.reason)


@dataclass
class Meta:
    """Everything known about a response other than the rows themselves."""

    dataset: str
    route: str
    row_count: int = 0

    # --- completeness -----------------------------------------------------
    truncated: bool = False
    """True when the row limit was hit on a route with no offset support."""
    limit_used: Optional[int] = None
    supports_offset: bool = False
    offset_ignored: bool = False
    """True when the route accepted `offset` but returned the same page anyway."""

    # --- plan / status ----------------------------------------------------
    tier_required: Optional[str] = None
    registry_status: Optional[str] = None

    # --- point in time ----------------------------------------------------
    as_of_requested: Optional[str] = None
    as_of_mode: Optional[str] = None
    as_of_applied: bool = False
    as_of_field: Optional[str] = None
    """The column the filter actually used (``knowledge_date`` when the server
    supplies it, otherwise the declared knowledge_time_field)."""
    knowledge_time_field: Optional[str] = None
    point_in_time_safe: Optional[bool] = None
    pit_caveat: Optional[str] = None
    knowledge_date_present: bool = False
    knowledge_date_imputed_rows: Optional[int] = None
    """How many returned rows carry ``kd_imputed=true``. None when the server
    does not send the field at all."""
    knowledge_date_sources: List[str] = field(default_factory=list)
    """Distinct ``kd_source`` values seen, e.g. ``["statutory_deadline"]``."""

    # --- coverage and gaps ------------------------------------------------
    data_gaps: List[Gap] = field(default_factory=list)
    gaps_source: str = "unknown"
    """``server`` | ``client_derived`` | ``unsupported`` | ``unknown``."""
    coverage_min: Optional[str] = None
    coverage_max: Optional[str] = None

    # --- provenance -------------------------------------------------------
    data_as_of: Optional[str] = None
    source_role: Optional[str] = None
    lineage: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    status_code: Optional[int] = None

    warnings: List[str] = field(default_factory=list)
    raw_envelope_keys: List[str] = field(default_factory=list)
    row_key: Optional[str] = None
    """Which envelope key held the rows: ``rows`` / ``items`` / ``data``."""

    def __str__(self) -> str:
        bits = ["%s rows=%d" % (self.dataset, self.row_count)]
        if self.truncated:
            bits.append("TRUNCATED")
        if self.as_of_requested:
            bits.append("as_of=%s(%s,%s)" % (
                self.as_of_requested, self.as_of_mode,
                "applied" if self.as_of_applied else "not applied"))
        if self.knowledge_date_imputed_rows:
            bits.append("kd_imputed=%d" % self.knowledge_date_imputed_rows)
        if self.data_gaps:
            bits.append("gaps=%d(%s)" % (len(self.data_gaps), self.gaps_source))
        return "Meta(" + ", ".join(bits) + ")"
