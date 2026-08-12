"""Paid-tier behaviour, replayed from recorded responses. No API key needed.

63 key-gated datasets were recorded on 2026-08-12 with a restricted key that was
deleted afterwards. Auth headers are redacted; `test_audit_gate.py` asserts that.

These are the tests that would otherwise be impossible in CI, and several of
them pin findings that only showed up once real paid responses were in hand.
"""
from __future__ import annotations

import glob
import json
import os

import pytest

import twmd
from twmd.envelope import extract_rows
from twmd.pit import scan_knowledge_dates

CASSETTE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cassettes")


def load(dataset: str):
    path = os.path.join(CASSETTE_DIR, "%s.json" % dataset)
    if not os.path.exists(path):
        pytest.skip("cassette %s not recorded" % dataset)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def all_cassettes():
    return sorted(glob.glob(os.path.join(CASSETTE_DIR, "*.json")))


pytestmark = pytest.mark.skipif(not all_cassettes(), reason="no cassettes recorded")


# ------------------------------------------------------------------ coverage
def test_every_key_gated_dataset_was_recorded():
    recorded = {os.path.basename(p)[:-5] for p in all_cassettes()}
    expected = {k for k in twmd.datasets()
                if twmd.get(k).free_tier_probe == "needs_key"}
    assert expected - recorded == set()


# ------------------------------------------------------- envelope shapes
def test_rows_live_under_four_different_keys():
    """Census across 52 successful paid responses.

    Nine datasets put their rows at ``envelope.data``. Before the nested lookup
    existed the SDK returned an empty frame for every one of them -- which reads
    as "no data for this ticker", not as "the SDK could not find the rows".
    """
    seen = {}
    for path in all_cassettes():
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        if c["response"]["status"] != 200:
            continue
        _, key = extract_rows(c["response"]["body"])
        seen.setdefault(key, []).append(c["dataset"])

    assert set(seen) >= {"data", "rows", "envelope.data"}
    assert len(seen["envelope.data"]) >= 9
    assert "price_enhanced" in seen["envelope.data"]


def test_price_enhanced_rows_are_nested_and_are_adjustment_factors():
    """Confirms appendix N and O together, on a real paid response.

    The rows are at ``envelope.data``, and they are adjustment factors -- not
    the OHLCV that the dataset contract declares. ``close`` never appears.
    """
    body = load("price_enhanced")["response"]["body"]
    rows, key = extract_rows(body)
    assert key == "envelope.data"
    assert rows, "price_enhanced returned no rows"

    columns = set(rows[0])
    assert {"event_type", "factor", "pre_event_close", "reference_price",
            "ticker", "trade_date"} <= columns
    assert "close" not in columns
    assert "volume" not in columns


def test_metadata_lists_in_real_responses_are_not_read_as_rows():
    # price_enhanced carries meta.mandatory_contract_fields_present, a list of
    # 11 strings sitting one level down, exactly where a naive descent would
    # find it first.
    body = load("price_enhanced")["response"]["body"]
    assert isinstance(body["meta"]["mandatory_contract_fields_present"], list)
    rows, key = extract_rows(body)
    assert key == "envelope.data"
    assert all(isinstance(r, dict) for r in rows)


# ---------------------------------------------------------- knowledge_date
FUNDAMENTALS = ["income_statement", "balance_sheet", "cash_flow_statement",
                "financial_ratios"]


@pytest.mark.parametrize("dataset", FUNDAMENTALS)
def test_knowledge_date_is_live_and_entirely_imputed(dataset):
    """WORKORDER_API_expose_knowledge_date, phase 1, as actually deployed.

    All four fundamentals now return knowledge_date -- and every row carries
    kd_imputed=true with kd_source=statutory_deadline. Not one observed
    announcement timestamp among them, which is precisely why the SDK warns
    rather than presenting these as observed disclosure dates.
    """
    rows, _ = extract_rows(load(dataset)["response"]["body"])
    scan = scan_knowledge_dates(rows)
    assert scan["present"] is True
    assert scan["non_null"] == len(rows)
    assert scan["imputed"] == len(rows)
    assert scan["sources"] == ["statutory_deadline"]


def test_monthly_revenue_is_probed_not_refused_outright():
    """Phase 1 reached monthly_revenue on 2026-08-12.

    The registry still classifies it client_unsafe -- its declared as_of_date is
    a period, not a disclosure date -- but the server now supplies a real
    knowledge_date, so the decision belongs to the response.
    """
    from twmd.pit import resolve_mode
    assert resolve_mode(twmd.get("monthly_revenue"), None) == "client_unsafe_probe"


def test_income_statement_report_date_is_empty_as_documented():
    """Confirms the WORKORDER's phase-3 claim on live paid rows.

    report_date is null across the board, so it cannot serve as a knowledge
    axis -- which is why knowledge_date is imputed from the filing deadline.
    """
    rows, _ = extract_rows(load("income_statement")["response"]["body"])
    assert rows
    assert all(r.get("report_date") is None for r in rows)


def test_margin_system_stats_maintenance_ratio_is_null_as_documented():
    """The documented honest gap, confirmed. The SDK leaves it NA."""
    rows, _ = extract_rows(load("margin_system_stats")["response"]["body"])
    assert rows
    assert all(r.get("maintenance_ratio") is None for r in rows)


# --------------------------------------------------------------- plan edges
def test_only_an_enterprise_dataset_is_still_out_of_reach():
    """After the entitlement fix, 62 of 63 key-gated datasets record 200.

    The one refusal left is macro_global, which is enterprise tier and
    private_beta -- a developer key not reaching it is correct, not a defect.
    The 403 commercial_use_not_allowed shape seen on 2026-08-12 is gone.
    """
    refused = []
    for path in all_cassettes():
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        if c["response"]["status"] != 200:
            refused.append((c["dataset"], c["response"]["status"],
                            c["response"]["body"].get("error")))
    assert refused == [("macro_global", 402, "not_entitled_for_dataset")]
    assert twmd.get("macro_global").tier == "enterprise"


def test_no_cassette_records_the_commercial_use_403_any_more():
    for path in all_cassettes():
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        assert c["response"]["body"].get("error") != "commercial_use_not_allowed", c["dataset"]


# ------------------------------------------------- undeclared required filters
def test_two_routes_demand_a_filter_the_api_spec_never_declares():
    """Both answer 400 missing_required_filter without naming the field.

    The working combinations were found by probing on 2026-08-12 and are carried
    in the registry so the SDK's error can name them.
    """
    assert twmd.get("interest_rate_snapshots").required_filters == ["rate_family", "rate_code"]
    assert twmd.get("market_breadth").required_filters == ["market", "date_from+date_to"]
    assert sum(1 for k in twmd.datasets() if twmd.get(k).required_filters) == 2


@pytest.mark.parametrize("dataset", ["interest_rate_snapshots", "market_breadth"])
def test_those_routes_return_data_once_the_filter_is_supplied(dataset):
    c = load(dataset)
    assert c["response"]["status"] == 200, dataset
    rows, _ = extract_rows(c["response"]["body"])
    assert rows, dataset
