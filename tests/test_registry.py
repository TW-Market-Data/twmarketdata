"""The registry must keep describing the API that was actually measured."""
from __future__ import annotations

import pytest

import twmd
from twmd.errors import DatasetNotFoundError


def test_ships_all_82_sellable_datasets():
    assert len(twmd.datasets()) == 82


def test_six_routes_are_not_the_kebab_case_of_their_key():
    # If this shrinks, a route was renamed and the registry needs regenerating.
    odd = [k for k in twmd.datasets()
           if twmd.get(k).route != "/v2/datasets/" + k.replace("_", "-")]
    assert sorted(odd) == [
        "financial_ratios", "industry_index", "interest_rate_snapshots",
        "issuer_profiles", "margin_short_total", "taifex_final_settlement",
    ]


def test_as_of_mode_distribution_matches_measurement():
    from collections import Counter
    modes = Counter(twmd.get(k).as_of_mode for k in twmd.datasets())
    assert dict(modes) == {
        "client": 45, "server": 16, "client_unsafe": 8,
        "client_unverified": 5, "unsupported": 8,
    }


def test_only_nine_routes_paginate():
    assert sum(1 for k in twmd.datasets() if twmd.get(k).supports_offset) == 9


def test_only_22_routes_report_gaps():
    assert sum(1 for k in twmd.datasets() if twmd.get(k).supports_data_gaps) == 22


def test_free_tier_allowlist_is_measured_not_declared():
    runnable = twmd.runnable_without_key()
    assert len(runnable) == 16
    # Declared free but measured 401: must NOT be in the runnable allowlist.
    for key in ("valuation_data", "issuer_profiles", "industry_index"):
        assert twmd.get(key).tier == "free"
        assert key not in runnable


def test_demo_symbols():
    assert twmd.free_tier_symbols() == ["2330", "2317", "2454", "0050", "2603"]


def test_lookup_accepts_route_slug_and_suggests_on_typo():
    assert twmd.get("monthly-revenue").key == "monthly_revenue"
    with pytest.raises(DatasetNotFoundError) as exc:
        twmd.get("monthly_revenu")
    assert "monthly_revenue" in str(exc.value)


def test_capabilities_exposes_the_honest_fields():
    caps = twmd.capabilities("monthly_revenue")
    assert caps["as_of"] == "client_unsafe"
    assert caps["point_in_time_safe"] is False
    assert caps["runnable_without_key"] is True
    assert "look ahead" in caps["as_of_note"]


def test_every_dataset_has_a_generated_method():
    c = twmd.Client()
    missing = [k for k in twmd.datasets() if not callable(getattr(c, k, None))]
    assert missing == []
