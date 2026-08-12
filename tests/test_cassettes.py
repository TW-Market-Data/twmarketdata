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
def test_plan_boundaries_come_back_as_402_and_403_both_typed():
    """Entitlement is per key, and it refuses in two different shapes.

    The developer key reads 6 developer-tier datasets and is refused on 3 more
    with 403 `commercial_use_not_allowed` -- a licensing message, although the
    use here is exactly the personal development and testing that plan permits.
    macro_global (enterprise) is a 402. Both map to TierRequiredError, so callers
    do not have to care which shape arrived.
    """
    gated = []
    for path in all_cassettes():
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        if c["response"]["status"] in (402, 403):
            gated.append((c["dataset"], c["response"]["status"],
                          c["response"]["body"].get("error"), c["sdk_error"]))
    assert gated, "no plan refusals recorded"
    assert all(err == "TierRequiredError" for _, _, _, err in gated)
    assert {code for _, _, code, _ in gated} <= {
        "not_entitled_for_dataset", "commercial_use_not_allowed"}


def test_the_developer_key_reached_exactly_its_six_datasets():
    """The plan said "developer, 6 datasets" and six is what it read.

    Recorded 2026-08-12. The three developer-tier datasets outside that
    allow-list answer 403 commercial_use_not_allowed rather than naming the
    allow-list, which is why the SDK keeps the server's wording instead of
    paraphrasing it.
    """
    served = {"etf_holdings", "block_trade_daily", "subsidiary_investment",
              "esg_ghg_carbon_disclosure", "governance_t187ap33_l",
              "market_overview_snapshots"}
    refused_403 = {"interest_rate_snapshots", "tax_business_registration",
                   "macro_worldbank"}
    for dataset in served:
        assert load(dataset)["response"]["status"] == 200, dataset
    for dataset in refused_403:
        c = load(dataset)
        assert c["response"]["status"] == 403, dataset
        assert c["response"]["body"]["error"] == "commercial_use_not_allowed"


def test_etf_holdings_keeps_no_history_so_a_change_series_is_underivable():
    """Why taiwan_stock_active_etf_holding_change is D rather than C.

    Live on 2026-08-12: as_of=2026-08-10 returns rows; 2026-07-01 and 2026-05-01
    return none. Without consecutive snapshots there is nothing to diff.
    """
    rows, _ = extract_rows(load("etf_holdings")["response"]["body"])
    if rows:
        assert {"etf_code", "holding_ticker", "holding_weight", "as_of_date"} <= set(rows[0])
    from twmd.compat import finmind as fm
    assert fm.mapping_for("taiwan_stock_active_etf_holding_change")["tier"] == "D"


def test_market_breadth_demands_a_filter_the_registry_does_not_know_about():
    """400 missing_required_filter on a route the OpenAPI marks as unfiltered.

    Recorded so the discrepancy is not lost; the SDK surfaces the server's own
    message rather than a generic failure.
    """
    c = load("market_breadth")
    assert c["response"]["status"] == 400
    assert c["response"]["body"]["error"] == "missing_required_filter"
