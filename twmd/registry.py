"""The generated dataset registry: routes, parameter names, PIT semantics, tiers.

The live API is not uniform -- entity parameters come in seven spellings, date
parameters in five, ``as_of`` exists on 17 of 82 routes, ``offset`` on 9, and six
routes are not the kebab-case of their dataset key. Rather than make callers
learn that, the SDK looks it up here.

Regenerate with ``tools/build_mapping.py`` then ``tools/gen_registry.py``.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping, Optional

from .errors import DatasetNotFoundError

__all__ = ["DatasetInfo", "datasets", "get", "capabilities", "free_tier_symbols",
           "runnable_without_key", "REGISTRY_MEASURED_ON", "DEFAULT_BASE_URL"]

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_registry.json")

with open(_PATH, encoding="utf-8") as _fh:
    _RAW: Dict[str, Any] = json.load(_fh)

REGISTRY_MEASURED_ON: str = _RAW["measured_on"]
DEFAULT_BASE_URL: str = _RAW["api_base_url"]
_FREE_SYMBOLS: List[str] = list(_RAW["free_tier_symbols"])


class DatasetInfo:
    """One dataset's route and semantics."""

    __slots__ = ("key", "_d")

    def __init__(self, key: str, d: Mapping[str, Any]) -> None:
        self.key = key
        self._d = d

    # --- identity ---------------------------------------------------------
    @property
    def route(self) -> str:
        return str(self._d["route"])

    @property
    def name_zh(self) -> Optional[str]:
        return self._d.get("name_zh")

    @property
    def category(self) -> Optional[str]:
        return self._d.get("category")

    @property
    def tier(self) -> str:
        return str(self._d["tier"])

    @property
    def status(self) -> str:
        return str(self._d["registry_status"])

    @property
    def grain(self) -> List[str]:
        return list(self._d.get("grain") or [])

    @property
    def columns(self) -> List[str]:
        return list(self._d.get("columns") or [])

    # --- parameters -------------------------------------------------------
    @property
    def entity_param(self) -> Optional[str]:
        return self._d.get("api_entity_param")

    @property
    def start_param(self) -> Optional[str]:
        return self._d.get("api_start_param")

    @property
    def end_param(self) -> Optional[str]:
        return self._d.get("api_end_param")

    @property
    def as_of_param(self) -> Optional[str]:
        return self._d.get("as_of_param")

    @property
    def other_params(self) -> List[str]:
        return list(self._d.get("api_other_params") or [])

    @property
    def supports_offset(self) -> bool:
        return bool(self._d.get("supports_offset"))

    @property
    def supports_data_gaps(self) -> bool:
        return bool(self._d.get("supports_data_gaps"))

    # --- point in time ----------------------------------------------------
    @property
    def as_of_mode(self) -> str:
        """``server`` | ``client`` | ``client_unsafe`` | ``client_unverified`` | ``unsupported``."""
        return str(self._d["as_of_mode"])

    @property
    def as_of_note(self) -> Optional[str]:
        return self._d.get("as_of_note")

    @property
    def knowledge_time_field(self) -> Optional[str]:
        return self._d.get("knowledge_time_field")

    @property
    def point_in_time_safe(self) -> bool:
        return bool(self._d.get("point_in_time_safe"))

    # --- coverage ---------------------------------------------------------
    @property
    def coverage_min(self) -> Optional[str]:
        return self._d.get("coverage_min")

    @property
    def coverage_max(self) -> Optional[str]:
        return self._d.get("coverage_max")

    @property
    def free_tier_probe(self) -> str:
        """Measured, not declared: what a no-key request actually returned.

        ``tier`` alone does not answer this -- three datasets declared ``free``
        (valuation_data, issuer_profiles, industry_index) returned 401 when
        every route was probed without a key.
        """
        return str(self._d.get("free_tier_probe"))

    @property
    def runnable_without_key(self) -> bool:
        return self.free_tier_probe == "yes_rows"

    def supported_filters(self) -> List[str]:
        out = []
        if self.entity_param:
            out.append("ticker")
        if self.start_param:
            out.append("start")
        if self.end_param:
            out.append("end")
        if self.as_of_mode != "unsupported":
            out.append("as_of")
        out.append("limit")
        if self.supports_offset:
            out.append("offset")
        out.extend(self.other_params)
        return out

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._d, dataset_key=self.key)

    def __repr__(self) -> str:
        return "<DatasetInfo %s tier=%s as_of=%s status=%s>" % (
            self.key, self.tier, self.as_of_mode, self.status)


_INFO: Dict[str, DatasetInfo] = {
    k: DatasetInfo(k, v) for k, v in _RAW["datasets"].items()
}


def datasets() -> List[str]:
    """All sellable dataset keys, sorted."""
    return sorted(_INFO)


def get(dataset: str) -> DatasetInfo:
    """Look up a dataset, with a helpful error for near-misses."""
    try:
        return _INFO[dataset]
    except KeyError:
        pass
    # Callers coming from the REST API often have the kebab route slug.
    guess = dataset.replace("-", "_")
    if guess in _INFO:
        return _INFO[guess]
    import difflib
    close = difflib.get_close_matches(guess, _INFO, n=3, cutoff=0.6)
    hint = (" Did you mean: %s?" % ", ".join(close)) if close else ""
    raise DatasetNotFoundError(
        "Unknown dataset %r. This SDK ships %d sellable datasets; "
        "twmd.datasets() lists them.%s" % (dataset, len(_INFO), hint),
        dataset=dataset,
    )


def capabilities(dataset: str) -> Dict[str, Any]:
    """What this dataset supports -- so callers never have to find out by trial."""
    d = get(dataset)
    return {
        "dataset": d.key,
        "name_zh": d.name_zh,
        "route": d.route,
        "tier": d.tier,
        "status": d.status,
        "grain": d.grain,
        "as_of": d.as_of_mode,
        "as_of_note": d.as_of_note,
        "knowledge_time_field": d.knowledge_time_field,
        "point_in_time_safe": d.point_in_time_safe,
        "data_gaps": "server" if d.supports_data_gaps else "client_derived_or_unknown",
        "pagination": "offset" if d.supports_offset else "limit_only",
        "filters": d.supported_filters(),
        "free_tier_probe": d.free_tier_probe,
        "runnable_without_key": d.runnable_without_key,
        "coverage": {"min": d.coverage_min, "max": d.coverage_max},
        "measured_on": REGISTRY_MEASURED_ON,
    }


def free_tier_symbols() -> List[str]:
    """The demo symbols that work without an API key."""
    return list(_FREE_SYMBOLS)


def runnable_without_key() -> List[str]:
    """Datasets measured to return rows with no API key.

    This is the allowlist the README examples are built from.
    """
    return sorted(k for k, v in _INFO.items() if v.runnable_without_key)
