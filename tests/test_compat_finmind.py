"""Compat layer: what it serves, what it refuses, and why it refuses loudly."""
from __future__ import annotations

import pytest

import twmd
from twmd.compat import finmind as fm
from twmd.errors import NotMappedError
from twmd.meta import CompatSubstitutionWarning
from conftest import FakeResponse, rows_envelope


@pytest.fixture(autouse=True)
def _client(session):
    c = twmd.Client(session=session)
    fm.set_client(c)
    yield c
    fm._client = None


def test_mapping_table_is_the_reviewed_one():
    assert "FinMind v2.0.7" in fm.FINMIND_SOURCE
    assert len(fm._METHODS) == 106


def test_a_grade_call_returns_data(session):
    session.queue = [
        FakeResponse(rows_envelope([{"symbol": "2330", "date": "2026-08-10", "close": 2380}])),
        FakeResponse(rows_envelope([])),
    ]
    df = fm.taiwan_stock_daily(stock_id="2330", start_date="2026-08-01")
    assert len(df) == 1


def test_unavailable_call_raises_instead_of_returning_an_empty_frame():
    # An empty frame here would be read as "no broker flow for this ticker",
    # which is a different claim from "TWMD does not carry broker flow".
    with pytest.raises(NotMappedError) as exc:
        fm.taiwan_stock_trading_daily_report(stock_id="2330")
    assert "no TW Market Data equivalent" in str(exc.value)
    assert "broker" in str(exc.value).lower()


def test_non_taiwan_calls_refuse():
    with pytest.raises(NotMappedError, match="Non-Taiwan"):
        fm.us_stock_price(stock_id="AAPL")


def test_low_confidence_mapping_is_withheld_not_guessed():
    with pytest.raises(NotMappedError) as exc:
        fm.taiwan_stock_market_value(stock_id="2330")
    assert "not been verified row by row" in str(exc.value)
    assert "valuation_core_daily" in str(exc.value)      # candidate is still named


def test_substitution_warns_about_the_difference(session):
    session.queue = [FakeResponse(rows_envelope([{"ticker": "2330", "net_buy": 100}]))]
    with pytest.warns(CompatSubstitutionWarning, match="not a like-for-like"):
        fm.taiwan_stock_institutional_investors(stock_id="2330")


def test_vix_substitution_names_the_actual_difference():
    entry = fm.mapping_for("taiwan_option_vix")
    assert entry["twmd"] == ["taifex_atm_iv"]
    assert "NOT the official VIX" in entry["note"]


def test_b_grade_without_a_reshaper_refuses_and_points_at_the_native_call():
    with pytest.raises(NotMappedError) as exc:
        fm.taiwan_stock_financial_statement(stock_id="2330")
    assert "different row shape" in str(exc.value)
    assert "income_statement" in str(exc.value)


def test_unknown_call_is_reported_against_the_introspected_surface():
    with pytest.raises(NotMappedError, match="not a recognised FinMind call"):
        fm._call("taiwan_stock_definitely_not_real")


def test_supported_and_unsupported_partition_the_table():
    supported = set(fm.supported_calls())
    unsupported = set(fm.unsupported_calls())
    assert supported.isdisjoint(unsupported)
    assert supported | unsupported == set(fm._METHODS)
    assert len(supported) > 25


def test_login_by_token_configures_a_twmd_key():
    client = fm.login_by_token("sk_test_notreal")
    assert client.has_api_key is True
    fm._client = None


def test_stock_id_alias_added_when_pandas_present(session):
    if not twmd.pandas_available():
        pytest.skip("pandas not installed")
    session.queue = [FakeResponse(rows_envelope([{"ticker": "2330", "holding_pct": 70.0}]))]
    df = fm.taiwan_stock_shareholding(stock_id="2330")
    assert "stock_id" in df.columns and df["stock_id"].iloc[0] == "2330"


def test_free_tier_symbol_guard_still_applies(session):
    with pytest.raises(twmd.FreeTierSymbolError):
        fm.taiwan_stock_month_revenue(stock_id="1101")
