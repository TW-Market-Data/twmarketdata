"""Client behaviour: parameter translation, free tier, truncation, gaps, transport."""
from __future__ import annotations

import pytest

import twmd
from twmd.errors import (FreeTierSymbolError, MissingApiKeyError, RateLimitedError,
                         TwmdConfigError, UnsupportedParameterError)
from twmd.meta import TruncatedResultWarning
from conftest import FakeResponse, rows_envelope


# ---------------------------------------------------------------- base url
def test_base_url_does_not_double_the_v2_segment(client, session):
    client.dataset("monthly_revenue", ticker="2330")
    assert session.calls[0]["url"] == "https://api.twmarketdata.com/v2/datasets/monthly-revenue"


def test_default_base_url_is_the_live_api_not_the_retired_gateway():
    assert twmd.DEFAULT_BASE_URL == "https://api.twmarketdata.com/v2"
    assert "twmarketdata.com/v2" in twmd.Client()._transport.base_url


# ------------------------------------------------------ parameter translation
def test_ticker_is_translated_per_route(client, session):
    client.dataset("monthly_revenue", ticker="2330")   # route wants `symbol`
    assert session.calls[0]["params"]["symbol"] == "2330"

    client.dataset("foreign_holding", ticker="2330")   # route wants `ticker`
    assert session.calls[1]["params"]["ticker"] == "2330"


def test_dates_are_translated_per_route(client, session):
    client.dataset("monthly_revenue", ticker="2330", start="2024-01-01", end="2024-12-31")
    p = session.calls[0]["params"]
    assert p["start_date"] == "2024-01-01" and p["end_date"] == "2024-12-31"

    client.dataset("foreign_holding", ticker="2330", start="2024-01-01")
    assert session.calls[1]["params"]["date_from"] == "2024-01-01"


def test_unsupported_parameter_is_an_error_not_a_silent_drop(client):
    # margin_short_total has no entity parameter. Dropping ticker quietly would
    # return the whole market while looking like a single-ticker query.
    with pytest.raises(UnsupportedParameterError) as exc:
        client.dataset("margin_short_total", ticker="2330")
    assert "does not accept" in str(exc.value)


def test_unknown_extra_parameter_rejected(client):
    with pytest.raises(UnsupportedParameterError):
        client.dataset("monthly_revenue", ticker="2330", nonsense=1)


def test_offset_rejected_where_the_route_lacks_it(client):
    with pytest.raises(UnsupportedParameterError):
        client.dataset("monthly_revenue", ticker="2330", offset=100)


def test_gap_flag_sent_only_where_supported(client, session):
    client.dataset("foreign_holding", ticker="2330")          # supports it
    assert session.calls[0]["params"].get("include_data_gaps") == "true"
    client.dataset("monthly_revenue", ticker="2330")          # does not
    assert "include_data_gaps" not in session.calls[1]["params"]


# ------------------------------------------------------------------ free tier
def test_free_tier_rejects_non_demo_symbols_with_the_list(client):
    with pytest.raises(FreeTierSymbolError) as exc:
        client.dataset("monthly_revenue", ticker="1101")
    assert "2330" in str(exc.value) and "0050" in str(exc.value)


@pytest.mark.parametrize("symbol", ["2330", "2317", "2454", "0050", "2603"])
def test_all_five_demo_symbols_pass(client, symbol):
    client.dataset("monthly_revenue", ticker=symbol)


def test_any_symbol_allowed_once_a_key_is_present(session):
    c = twmd.Client("sk_test_notreal", session=session)
    c.dataset("monthly_revenue", ticker="1101")
    assert session.calls[0]["headers"]["X-API-Key"] == "sk_test_notreal"


def test_key_read_from_environment(monkeypatch, session):
    monkeypatch.setenv("TWMD_API_KEY", "sk_env")
    assert twmd.Client(session=session).has_api_key is True


def test_empty_key_is_a_configuration_error():
    with pytest.raises(TwmdConfigError):
        twmd.Client("   ")


def test_key_never_appears_in_repr():
    # Deliberately not shaped like a real key: the pre-publish secret scanner
    # flags live-key patterns wherever they appear, including in fixtures.
    r = repr(twmd.Client("notarealkey-supersecret"))
    assert "supersecret" not in r and "***" in r


# ---------------------------------------------------------------- truncation
def test_hitting_the_limit_without_offset_support_is_flagged(session):
    c = twmd.Client(session=session, default_limit=2)
    session.queue = [FakeResponse(rows_envelope([{"a": 1}, {"a": 2}]))]
    with pytest.warns(TruncatedResultWarning, match="incomplete"):
        df = c.dataset("monthly_revenue", ticker="2330")
    assert c.last_meta.truncated is True


def test_short_result_is_not_flagged(session):
    c = twmd.Client(session=session, default_limit=10)
    session.queue = [FakeResponse(rows_envelope([{"a": 1}]))]
    c.dataset("monthly_revenue", ticker="2330")
    assert c.last_meta.truncated is False


def test_offset_routes_paginate_to_completion(session):
    c = twmd.Client(session=session, default_limit=2)
    session.queue = [
        FakeResponse(rows_envelope([{"a": 1}, {"a": 2}])),
        FakeResponse(rows_envelope([{"a": 3}])),
    ]
    c.dataset("securities_lending", ticker="2330")     # one of the 9 offset routes
    assert c.last_meta.row_count == 3
    assert c.last_meta.truncated is False
    assert session.calls[1]["params"]["offset"] == 2


# --------------------------------------------------------------------- meta
def test_meta_records_row_key_and_provenance(session):
    c = twmd.Client(session=session)
    session.queue = [FakeResponse(rows_envelope(
        [{"a": 1}], key="items", data_as_of="2026-08-10", source_role="official_twse",
        lineage={"provider": "TWSE"}))]
    c.dataset("monthly_revenue", ticker="2330")
    m = c.last_meta
    assert m.row_key == "items"
    assert m.data_as_of == "2026-08-10"
    assert m.source_role == "official_twse"
    assert m.lineage == {"provider": "TWSE"}
    assert m.request_id == "req_test"


def test_absent_gap_info_is_reported_as_such_not_as_no_gaps(session):
    c = twmd.Client(session=session)
    session.queue = [FakeResponse(rows_envelope([{"a": 1}]))]
    c.dataset("monthly_revenue", ticker="2330")
    assert c.last_meta.gaps_source in {"unsupported", "unknown"}
    assert c.last_meta.data_gaps == []


def test_server_gaps_are_passed_through(session):
    c = twmd.Client(session=session)
    session.queue = [FakeResponse(rows_envelope(
        [{"a": 1}], data_gaps=[{"start": "2024-01-02", "end": "2024-01-03",
                                "reason": "source_not_published"}]))]
    c.dataset("foreign_holding", ticker="2330")
    assert c.last_meta.gaps_source == "server"
    assert c.last_meta.data_gaps[0].reason == "source_not_published"


def test_non_active_dataset_warns(session):
    c = twmd.Client(session=session)
    session.queue = [FakeResponse(rows_envelope([{"a": 1}]))]
    with pytest.warns(twmd.DatasetStatusWarning, match="not a full production dataset"):
        c.dataset("dividends", ticker="2330")


# ---------------------------------------------------------------- transport
def test_403_temporarily_blocked_is_retried_then_raised_as_a_rate_limit(session):
    c = twmd.Client(session=session, max_retries=1)
    c._transport._sleep = lambda _s: None
    blocked = FakeResponse({"error": "temporarily_blocked"}, status_code=403)
    session.queue = [blocked, blocked]
    with pytest.raises(RateLimitedError):
        c.dataset("monthly_revenue", ticker="2330")
    assert len(session.calls) == 2          # retried, not given up on immediately


def test_transient_block_then_success(session):
    c = twmd.Client(session=session, max_retries=2)
    c._transport._sleep = lambda _s: None
    session.queue = [
        FakeResponse({"error": "temporarily_blocked"}, status_code=403),
        FakeResponse(rows_envelope([{"a": 1}])),
    ]
    c.dataset("monthly_revenue", ticker="2330")
    assert c.last_meta.row_count == 1


def test_401_is_not_retried(session):
    c = twmd.Client("sk_test", session=session, max_retries=3)
    session.queue = [FakeResponse({"error": "missing_api_key", "message": "no key"},
                                  status_code=401)]
    with pytest.raises(MissingApiKeyError):
        c.dataset("income_statement", ticker="2330")
    assert len(session.calls) == 1


def test_concurrency_default_is_conservative():
    # Four concurrent requests tripped a multi-minute block during measurement.
    c = twmd.Client()
    assert c._transport._semaphore._initial_value == 2


# -------------------------------------------------------------- daily_price
def test_daily_price_merges_boards_and_labels_market(session):
    c = twmd.Client(session=session)
    session.queue = [
        FakeResponse(rows_envelope([{"symbol": "2330", "date": "2026-08-10", "close": 2380}])),
        FakeResponse(rows_envelope([])),
    ]
    rows = c.daily_price("2330", raw=True)
    assert rows[0]["market"] == "TWSE"
    assert c.last_meta.dataset == "daily_price"


def test_daily_price_keeps_cross_board_duplicates_and_says_so(session):
    c = twmd.Client(session=session)
    same = {"symbol": "2330", "date": "2026-08-10", "close": 1}
    session.queue = [
        FakeResponse(rows_envelope([dict(same)])),
        FakeResponse(rows_envelope([dict(same)])),
    ]
    rows = c.daily_price("2330", raw=True)
    assert len(rows) == 2                                   # not silently deduped
    assert any("both boards" in w for w in c.last_meta.warnings)


# ------------------------------------------------- offset accepted but ignored
def test_offset_ignored_by_server_stops_instead_of_duplicating(session):
    # Measured 2026-08-12 on index-constituents: offset=0/3/6 returned the
    # identical page. Without detection the loop appends the same rows forever
    # and presents the duplicates as a full history.
    page = rows_envelope([{"a": 1}, {"a": 2}])
    c = twmd.Client(session=session, default_limit=2)
    session.queue = [FakeResponse(dict(page)), FakeResponse(dict(page)),
                     FakeResponse(dict(page))]
    with pytest.warns(TruncatedResultWarning, match="does not actually paginate"):
        c.dataset("index_constituents")
    assert c.last_meta.row_count == 2          # not 4, not 6
    assert c.last_meta.offset_ignored is True
    assert c.last_meta.truncated is True       # incomplete, and says so
    assert len(session.calls) == 2             # stopped at the repeat


def test_genuine_pagination_still_completes(session):
    c = twmd.Client(session=session, default_limit=2)
    session.queue = [
        FakeResponse(rows_envelope([{"a": 1}, {"a": 2}])),
        FakeResponse(rows_envelope([{"a": 3}, {"a": 4}])),
        FakeResponse(rows_envelope([{"a": 5}])),
    ]
    c.dataset("index_constituents")
    assert c.last_meta.row_count == 5
    assert c.last_meta.offset_ignored is False
    assert c.last_meta.truncated is False


# --------------------------------------------- entity params that aren't tickers
def test_native_entity_name_accepted_for_non_ticker_routes(client, session):
    # warrants_reference is keyed by `issuer`. Forcing it through ticker= sends a
    # stock code as an issuer code, and the API answers 0 rows without erroring.
    client.dataset("warrants_reference", issuer="元大")
    assert session.calls[0]["params"]["issuer"] == "元大"


def test_capabilities_says_when_the_entity_is_not_a_stock_ticker():
    caps = twmd.capabilities("warrants_reference")
    assert caps["entity_param"] == "issuer"
    assert caps["entity_is_stock_ticker"] is False
    assert "issuer" in caps["filters"]

    caps = twmd.capabilities("monthly_revenue")
    assert caps["entity_is_stock_ticker"] is True


def test_giving_both_names_is_an_error_not_a_silent_pick(client):
    with pytest.raises(UnsupportedParameterError):
        client.dataset("warrants_reference", ticker="2330", issuer="元大")


def test_free_tier_guard_does_not_fire_on_issuer_keyed_routes(client, session):
    # The five-demo-symbol rule is about stock tickers; an issuer code is not one.
    client.dataset("warrants_reference", issuer="not-a-demo-symbol")
    assert session.calls[0]["params"]["issuer"] == "not-a-demo-symbol"


# ------------------------------------------------------- per-route row caps
def test_limit_is_clamped_to_the_route_cap(session):
    # financial_ratios caps at 1000. Sending the 5000 default returns
    # 422 "limit: Input should be less than or equal to 1000" -- measured
    # against the live API on 2026-08-12.
    c = twmd.Client(session=session)          # default_limit is 5000
    c.dataset("financial_ratios", ticker="2330")
    assert session.calls[0]["params"]["limit"] == 1000


def test_five_different_route_caps_are_all_respected(session):
    c = twmd.Client(session=session)
    for dataset, expected in (("company_news", 100), ("security_master", 500),
                              ("financial_ratios", 1000), ("trading_calendar", 2000),
                              ("twse_daily_price", 5000)):
        assert twmd.get(dataset).limit_max == expected
        session.calls.clear()
        c.dataset(dataset, ticker="2330" if twmd.get(dataset).entity_param else None)
        assert session.calls[0]["params"]["limit"] == expected, dataset


def test_an_explicit_over_cap_limit_warns_rather_than_silently_shrinking(session):
    c = twmd.Client(session=session)
    with pytest.warns(TruncatedResultWarning, match="reduced to 100"):
        c.dataset("company_news", ticker="2330", limit=4000)
    assert session.calls[0]["params"]["limit"] == 100


def test_422_and_400_are_validation_errors_not_generic_failures(session):
    c = twmd.Client(session=session, max_retries=0)
    session.queue = [FakeResponse(
        {"error": "validation_error", "message": "limit: Input should be less than or equal to 1000"},
        status_code=422)]
    with pytest.raises(twmd.ValidationError) as exc:
        c.dataset("financial_ratios", ticker="2330")
    assert "less than or equal to 1000" in str(exc.value)   # server wording kept

    session.queue = [FakeResponse({"error": "missing_required_filter",
                                   "message": "Missing required filter"}, status_code=400)]
    with pytest.raises(twmd.ValidationError):
        c.dataset("market_breadth")


def test_server_enforced_cap_overrides_a_stale_spec(session):
    # margin_system_stats declares limit<=5000 in the OpenAPI and rejects
    # anything over 1000. The server names the real cap in its 422, so the SDK
    # honours it once rather than failing a call nobody could have got right.
    c = twmd.Client(session=session, max_retries=1)
    c._transport._sleep = lambda _s: None
    session.queue = [
        FakeResponse({"error": "validation_error",
                      "message": "limit: Input should be less than or equal to 1000"},
                     status_code=422),
        FakeResponse(rows_envelope([{"a": 1}])),
    ]
    with pytest.warns(TruncatedResultWarning, match="enforces limit<=1000"):
        c.dataset("margin_system_stats")
    assert session.calls[0]["params"]["limit"] == 5000
    assert session.calls[1]["params"]["limit"] == 1000
    assert c.last_meta.row_count == 1


def test_the_correction_does_not_loop(session):
    c = twmd.Client(session=session, max_retries=1)
    c._transport._sleep = lambda _s: None
    reject = FakeResponse({"error": "validation_error",
                           "message": "limit: Input should be less than or equal to 1000"},
                          status_code=422)
    session.queue = [reject, reject, reject]
    with pytest.warns(TruncatedResultWarning):
        with pytest.raises(twmd.ValidationError):
            c.dataset("margin_system_stats")
    assert len(session.calls) <= 3
