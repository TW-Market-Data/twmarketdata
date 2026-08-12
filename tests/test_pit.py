"""Point-in-time behaviour.

These are the tests that stop the SDK from quietly producing look-ahead. Each
one pins a refusal or a warning that a "helpful" refactor would otherwise
optimise away.
"""
from __future__ import annotations

import pytest

import twmd
from twmd.errors import PointInTimeUnavailable
from twmd.meta import (ImputedKnowledgeDateWarning, PITDataMissingWarning,
                       TruncatedPointInTimeWarning)
from twmd.pit import apply_as_of, resolve_mode, scan_knowledge_dates
from twmd.meta import Meta


def _meta(key="monthly_revenue"):
    return Meta(dataset=key, route=twmd.get(key).route)


# ------------------------------------------------------------------ refusals
def test_as_of_refused_when_there_is_no_knowledge_axis():
    with pytest.raises(PointInTimeUnavailable) as exc:
        resolve_mode(twmd.get("company_industry_exposures"), None)
    assert "company_industry_exposures" in str(exc.value)


def test_as_of_refused_on_a_route_that_accepts_it_but_cannot_mean_it():
    # subsidiary_investment's route takes as_of_date, but describe_dataset says
    # it has no knowledge axis. Semantics beat the parameter list.
    info = twmd.get("subsidiary_investment")
    assert info.as_of_param == "as_of"      # the route does accept it
    with pytest.raises(PointInTimeUnavailable):
        resolve_mode(info, None)


def test_monthly_revenue_as_of_refused_by_default():
    # as_of_date is the revenue PERIOD, not the announcement date. Filtering on
    # it would treat June revenue as known on June 30 when it is disclosed in July.
    with pytest.raises(PointInTimeUnavailable) as exc:
        resolve_mode(twmd.get("monthly_revenue"), None)
    assert "declared_field" in str(exc.value)


def test_unsafe_as_of_available_only_via_explicit_opt_in():
    assert resolve_mode(twmd.get("monthly_revenue"), "declared_field") == "client_unsafe"


def test_safe_datasets_need_no_opt_in():
    assert resolve_mode(twmd.get("twse_daily_price"), None) == "client"
    assert resolve_mode(twmd.get("balance_sheet"), None) == "server"


def test_client_refuses_before_spending_a_request(client, session):
    with pytest.raises(PointInTimeUnavailable):
        client.dataset("company_peer_groups", as_of="2024-01-01")
    assert session.calls == []


# ---------------------------------------------------- knowledge_date handling
def test_scan_reports_absence_rather_than_assuming():
    out = scan_knowledge_dates([{"a": 1}])
    assert out == {"present": False, "non_null": 0, "imputed": None, "sources": []}


def test_server_knowledge_date_is_used_and_imputation_is_surfaced():
    # The shape the API is adding per WORKORDER_API_expose_knowledge_date.
    rows = [
        {"month": "2026-05", "revenue": 1, "knowledge_date": "2026-06-10",
         "kd_imputed": True, "kd_source": "statutory_deadline"},
        {"month": "2026-06", "revenue": 2, "knowledge_date": "2026-07-10",
         "kd_imputed": True, "kd_source": "statutory_deadline"},
    ]
    meta = _meta()
    with pytest.warns(ImputedKnowledgeDateWarning, match="statutory filing deadline"):
        kept = apply_as_of(list(rows), info=twmd.get("monthly_revenue"),
                           as_of="2026-06-30", mode="client_unsafe",
                           meta=meta, truncated=False)
    assert [r["month"] for r in kept] == ["2026-05"]      # July disclosure excluded
    assert meta.as_of_field == "knowledge_date"
    assert meta.knowledge_date_imputed_rows == 2
    assert meta.knowledge_date_sources == ["statutory_deadline"]
    assert meta.as_of_applied is True


def test_observed_knowledge_dates_do_not_warn():
    rows = [{"knowledge_date": "2026-06-10", "kd_imputed": False, "kd_source": "mops_announcement"}]
    meta = _meta()
    import warnings as _w
    with _w.catch_warnings():
        _w.simplefilter("error", ImputedKnowledgeDateWarning)
        kept = apply_as_of(rows, info=twmd.get("monthly_revenue"), as_of="2026-06-30",
                           mode="client_unsafe", meta=meta, truncated=False)
    assert len(kept) == 1
    assert meta.knowledge_date_imputed_rows == 0


# ------------------------------------------------------------- null knowledge
def test_all_null_knowledge_column_warns_and_does_not_filter():
    # Production reality on monthly_revenue: announcement_date is null.
    rows = [{"month": "2026-06", "as_of_date": None}, {"month": "2026-05", "as_of_date": None}]
    meta = _meta()
    with pytest.warns(PITDataMissingWarning, match="null in every returned row"):
        kept = apply_as_of(rows, info=twmd.get("monthly_revenue"), as_of="2020-01-01",
                           mode="client_unsafe", meta=meta, truncated=False)
    assert kept == rows              # unchanged rows, not a silent empty frame
    assert meta.as_of_applied is False


def test_no_knowledge_column_at_all_warns_and_does_not_filter():
    meta = Meta(dataset="derivatives_market", route="/x")
    info = twmd.get("index_constituents")
    rows = [{"whatever": 1}]
    meta2 = _meta("index_constituents")
    with pytest.warns(PITDataMissingWarning):
        kept = apply_as_of(rows, info=info, as_of="2024-01-01", mode="client_unverified",
                           meta=meta2, truncated=False)
    assert kept == rows and meta2.as_of_applied is False


# ----------------------------------------------------------------- truncation
def test_truncated_client_side_as_of_warns():
    rows = [{"trade_date": "2024-01-02"}]
    meta = _meta("twse_daily_price")
    with pytest.warns(TruncatedPointInTimeWarning, match="does not prove"):
        apply_as_of(rows, info=twmd.get("twse_daily_price"), as_of="2024-06-01",
                    mode="client", meta=meta, truncated=True)


# ------------------------------------------------------------- date compare
def test_month_grained_column_survives_a_day_grained_cutoff():
    rows = [{"knowledge_date": "2026-06"}, {"knowledge_date": "2026-07"}]
    meta = _meta()
    kept = apply_as_of(rows, info=twmd.get("monthly_revenue"), as_of="2026-06-30",
                       mode="client_unsafe", meta=meta, truncated=False)
    assert [r["knowledge_date"] for r in kept] == ["2026-06"]


# ------------------------------------------- declared column vs projected column
def test_declared_column_resolved_through_a_verified_alias():
    # twse_daily_price declares trade_date (the DB column) but the API projects
    # it as `date`. Measured against the live response on 2026-08-12.
    from twmd.pit import resolve_field
    rows = [{"symbol": "2330", "date": "2026-08-10", "close": 2380}]
    assert resolve_field("trade_date", rows) == "date"


def test_period_columns_are_never_aliased_to_a_knowledge_date():
    # monthly_revenue returns month / revenue_month. Treating either as the
    # knowledge axis is the look-ahead this module exists to prevent.
    from twmd.pit import resolve_field
    rows = [{"symbol": "2330", "month": "2026-06", "revenue_month": "2026-06"}]
    assert resolve_field("as_of_date", rows) is None


def test_alias_makes_daily_price_as_of_actually_filter():
    rows = [{"date": "2026-08-10"}, {"date": "2026-05-02"}]
    meta = _meta("twse_daily_price")
    kept = apply_as_of(rows, info=twmd.get("twse_daily_price"), as_of="2026-06-30",
                       mode="client", meta=meta, truncated=False)
    assert [r["date"] for r in kept] == ["2026-05-02"]
    assert meta.as_of_applied is True and meta.as_of_field == "date"


def test_absent_column_is_reported_as_absent_not_as_null():
    rows = [{"symbol": "2330", "month": "2026-06"}]
    meta = _meta()
    with pytest.warns(PITDataMissingWarning, match="is not present in the response"):
        kept = apply_as_of(rows, info=twmd.get("monthly_revenue"), as_of="2026-06-30",
                           mode="client_unsafe", meta=meta, truncated=False)
    assert kept == rows and meta.as_of_applied is False


def test_server_side_as_of_still_warns_about_imputed_dates(session):
    """Measured 2026-08-12: the four fundamentals return kd_imputed=true on
    every row. Server-mode filtering is still filtering on a statutory-deadline
    derivation, so it must warn like client mode does -- otherwise the people
    running server-side PIT backtests are the only ones not told."""
    from conftest import FakeResponse, rows_envelope
    c = twmd.Client(session=session)
    session.queue = [FakeResponse(rows_envelope([
        {"fiscal_year": 2026, "knowledge_date": "2026-05-15",
         "kd_imputed": True, "kd_source": "statutory_deadline"},
    ]))]
    assert twmd.get("income_statement").as_of_mode == "server"
    with pytest.warns(ImputedKnowledgeDateWarning, match="statutory filing deadline"):
        c.income_statement(ticker="2330", as_of="2026-06-30")
    assert c.last_meta.knowledge_date_imputed_rows == 1
    assert c.last_meta.knowledge_date_sources == ["statutory_deadline"]


def test_server_side_as_of_is_quiet_when_dates_are_observed(session):
    from conftest import FakeResponse, rows_envelope
    import warnings as _w
    c = twmd.Client(session=session)
    session.queue = [FakeResponse(rows_envelope([
        {"knowledge_date": "2026-05-15", "kd_imputed": False, "kd_source": "mops"},
    ]))]
    with _w.catch_warnings():
        _w.simplefilter("error", ImputedKnowledgeDateWarning)
        c.income_statement(ticker="2330", as_of="2026-06-30")
    assert c.last_meta.knowledge_date_imputed_rows == 0
