"""Offline tests for transport behaviour, error mapping and framing."""

from __future__ import annotations

import email.utils
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from twmd import Client, access, frames
from twmd import client as client_mod
from twmd.errors import (
    TwmdAuthError,
    TwmdPaymentRequired,
    TwmdRateLimitError,
    TwmdServerError,
    TwmdTransportError,
)

# Synthetic placeholder values. The envelope *shape* is what these tests pin
# down; the numbers are deliberately flat and fake so no fixture reads as a
# depiction of any real security's behaviour.
ENVELOPE = {
    "dataset": "twse_daily_price",
    "rows": [
        {"symbol": "0000", "date": "2026-01-02", "close": 100.0},
        {"symbol": "0000", "date": "2026-01-01", "close": 100.0},
    ],
    "count": 2,
    "data_as_of": "2026-07-17",
    "source_role": "official_twse",
    "lineage": {"provider": "TWSE", "not_investment_advice": True},
    "meta": {"last_trading_day": "2026-07-16"},
}


# Second observed envelope variant: security-master / market-index.
ITEMS_ENVELOPE = {
    "generated_at": "2026-07-20T17:10:20Z",
    "dataset_id": "security-master",
    "as_of_date": "2026-07-20",
    "row_count": 1,
    # Quoted verbatim from the API's own response. This is upstream wording
    # being preserved, not framing authored by this package.
    "survivorship_bias_warning": {
        "enabled": True,
        "level": "warning",
        "message": "Current security master is not point-in-time complete; "
        "survivorship bias may exist for backtests.",
    },
    "items": [
        {
            "ticker": "0000",
            "security_identity": {"ticker": "0000", "is_active": True},
            "market_identity": {"market": "TWSE"},
        }
    ],
}


def make_client(handler, **kwargs):
    kwargs.setdefault("backoff_factor", 0.0)
    return Client(transport=httpx.MockTransport(handler), **kwargs)


def test_envelope_metadata_lands_on_attrs():
    client = make_client(lambda req: httpx.Response(200, json=ENVELOPE))
    df = client.get_dataset("twse-daily-price", symbol="2330")

    assert list(df.columns) == ["symbol", "date", "close"]
    assert len(df) == 2
    assert df.attrs["data_as_of"] == "2026-07-17"
    assert df.attrs["source_role"] == "official_twse"
    assert "rows" not in df.attrs


def test_lineage_compliance_flag_passes_through_unmodified():
    client = make_client(lambda req: httpx.Response(200, json=ENVELOPE))
    df = client.get_dataset("twse-daily-price", symbol="2330")
    assert df.attrs["lineage"] == {"provider": "TWSE", "not_investment_advice": True}


def test_api_key_sent_as_header_when_present():
    seen = {}

    def handler(request):
        seen["key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, json=ENVELOPE)

    make_client(handler, api_key="sk_live_test").get_dataset("twse-daily-price")
    assert seen["key"] == "sk_live_test"


def test_no_header_in_key_free_mode(monkeypatch):
    monkeypatch.delenv("TWMD_API_KEY", raising=False)
    seen = {}

    def handler(request):
        seen["key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, json=ENVELOPE)

    client = make_client(handler)
    assert client.has_api_key is False
    client.get_dataset("twse-daily-price", symbol="2330")
    assert seen["key"] is None


def test_api_key_read_from_environment(monkeypatch):
    monkeypatch.setenv("TWMD_API_KEY", "sk_live_from_env")
    seen = {}

    def handler(request):
        seen["key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, json=ENVELOPE)

    make_client(handler).get_dataset("twse-daily-price")
    assert seen["key"] == "sk_live_from_env"


def test_401_maps_to_auth_error_with_access_hint(monkeypatch):
    monkeypatch.delenv("TWMD_API_KEY", raising=False)
    body = {"error": "missing_api_key", "message": "缺少 API 金鑰。"}
    client = make_client(lambda req: httpx.Response(401, json=body))

    with pytest.raises(TwmdAuthError) as info:
        client.get_dataset("twse-daily-price", symbol="1101")

    assert info.value.error_code == "missing_api_key"
    assert info.value.body == body
    # The hint must explain that 1101 is outside the sample-ticker set.
    assert "1101" in str(info.value)


# The live 402 contract, verified 2026-07-21.
PAYMENT_402 = {
    "error": "not_entitled_for_dataset",
    "message": "您的方案未包含此資料集。請升級方案以存取。",
    "payment": {
        "price": "pro",
        "credits_url": "https://twmarketdata.com/pricing",
        "purchase_hint": "upgrade_plan",
    },
}


class TestPaymentRequired402:
    """402 = valid key, insufficient plan. Distinct from 401 (no key)."""

    def test_maps_to_payment_required_with_full_body(self):
        client = make_client(lambda req: httpx.Response(402, json=PAYMENT_402))
        with pytest.raises(TwmdPaymentRequired) as info:
            client.get_dataset("institutional-flow", symbol="2330")
        assert info.value.body == PAYMENT_402          # nothing dropped
        assert info.value.error_code == "not_entitled_for_dataset"

    def test_payment_fields_exposed_on_exception(self):
        client = make_client(lambda req: httpx.Response(402, json=PAYMENT_402))
        with pytest.raises(TwmdPaymentRequired) as info:
            client.get_dataset("institutional-flow", symbol="2330")
        exc = info.value
        assert exc.payment == PAYMENT_402["payment"]
        assert exc.price == "pro"
        assert exc.credits_url == "https://twmarketdata.com/pricing"
        assert exc.purchase_hint == "upgrade_plan"

    def test_unknown_future_payment_fields_preserved(self):
        body = {
            "error": "not_entitled_for_dataset",
            "payment": {"price": "enterprise", "credits_url": "https://x", "future_field": "kept"},
        }
        client = make_client(lambda req: httpx.Response(402, json=body))
        with pytest.raises(TwmdPaymentRequired) as info:
            client.get_dataset("income-statement", symbol="2330")
        assert info.value.body["payment"]["future_field"] == "kept"
        assert info.value.price == "enterprise"

    def test_accessors_none_when_payment_absent(self):
        body = {"error": "not_entitled_for_dataset", "message": "no payment block"}
        client = make_client(lambda req: httpx.Response(402, json=body))
        with pytest.raises(TwmdPaymentRequired) as info:
            client.get_dataset("income-statement", symbol="2330")
        exc = info.value
        assert exc.payment is None
        assert exc.price is None and exc.credits_url is None and exc.purchase_hint is None
        assert exc.body == body                        # still preserved

    def test_402_is_not_retried(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(402, json=PAYMENT_402)

        with pytest.raises(TwmdPaymentRequired):
            make_client(handler).get_dataset("institutional-flow", symbol="2330")
        assert calls["n"] == 1                          # terminal, no retry

    def test_401_and_402_are_distinct(self):
        """401 = no key (register); 402 = plan too small (upgrade). Not the same."""
        assert not issubclass(TwmdPaymentRequired, TwmdAuthError)
        assert not issubclass(TwmdAuthError, TwmdPaymentRequired)


def test_terminal_status_is_not_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"error": "invalid_api_key"})

    with pytest.raises(TwmdAuthError):
        make_client(handler, api_key="bad").get_dataset("twse-daily-price")
    assert calls["n"] == 1


def test_429_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": "rate_limited"})
        return httpx.Response(200, json=ENVELOPE)

    df = make_client(handler).get_dataset("twse-daily-price")
    assert calls["n"] == 3
    assert len(df) == 2


def test_retries_exhausted_raises_last_error():
    def handler(request):
        return httpx.Response(503, json={"error": "unavailable"})

    with pytest.raises(TwmdServerError):
        make_client(handler, max_retries=2).get_dataset("twse-daily-price")


def test_rate_limit_error_after_exhaustion():
    def handler(request):
        return httpx.Response(429, json={"error": "rate_limited"})

    with pytest.raises(TwmdRateLimitError):
        make_client(handler, max_retries=1).get_dataset("twse-daily-price")


def test_network_failure_raises_transport_error():
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(TwmdTransportError):
        make_client(handler, max_retries=1).get_dataset("twse-daily-price")


def test_as_of_is_forwarded_verbatim():
    seen = {}

    def handler(request):
        seen["as_of"] = request.url.params.get("as_of")
        return httpx.Response(200, json=ENVELOPE)

    make_client(handler).get_dataset("income-statement", symbol="2330", as_of="2025-01-01")
    assert seen["as_of"] == "2025-01-01"


def test_as_of_omitted_when_not_given():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=ENVELOPE)

    make_client(handler).get_dataset("twse-daily-price", symbol="2330")
    assert "as_of" not in seen["params"]


class TestSourceMarker:
    """The integration source marker (§6 unified attribution)."""

    def test_source_attached_to_every_request(self):
        seen = {}

        def handler(request):
            seen["source"] = request.url.params.get("source")
            return httpx.Response(200, json=ENVELOPE)

        make_client(handler, source="ecosys/tradingagents").get_dataset("twse-daily-price")
        assert seen["source"] == "ecosys/tradingagents"

    def test_no_source_sent_when_unset(self):
        seen = {}

        def handler(request):
            seen["params"] = dict(request.url.params)
            return httpx.Response(200, json=ENVELOPE)

        make_client(handler).get_dataset("twse-daily-price", symbol="2330")
        assert "source" not in seen["params"]

    def test_per_call_source_overrides_client_source(self):
        seen = {}

        def handler(request):
            seen["source"] = request.url.params.get("source")
            return httpx.Response(200, json=ENVELOPE)

        client = make_client(handler, source="ecosys/dexter")
        client.get_dataset("twse-daily-price", source="ecosys/tradingagents")
        assert seen["source"] == "ecosys/tradingagents"

    def test_source_attached_on_pagination_and_catalog(self):
        seen = []

        def handler(request):
            seen.append(request.url.params.get("source"))
            return httpx.Response(200, json={"rows": [], "count": 0})

        client = make_client(handler, source="ecosys/migrate")
        list(client.iter_pages("twse-daily-price", limit=5))
        client.list_datasets()
        assert seen and all(s == "ecosys/migrate" for s in seen)

    def test_blank_source_is_treated_as_unset(self):
        seen = {}

        def handler(request):
            seen["params"] = dict(request.url.params)
            return httpx.Response(200, json=ENVELOPE)

        client = make_client(handler, source="   ")
        assert client.source is None
        client.get_dataset("twse-daily-price")
        assert "source" not in seen["params"]


def test_pagination_stops_when_offset_is_ignored():
    """Server re-sends page one regardless of offset — loop must not spin."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=ENVELOPE)  # always identical

    pages = list(make_client(handler).iter_pages("twse-daily-price", limit=2))
    assert len(pages) == 1
    assert calls["n"] == 2  # one yielded page, one repeat detected


def test_pagination_stops_on_short_page():
    def handler(request):
        return httpx.Response(200, json=ENVELOPE)  # 2 rows < limit of 10

    pages = list(make_client(handler).iter_pages("twse-daily-price", limit=10))
    assert len(pages) == 1


def test_pagination_walks_when_offset_works():
    def handler(request):
        offset = int(request.url.params.get("offset", 0))
        if offset >= 4:
            return httpx.Response(200, json={"rows": [], "count": 0})
        rows = [{"symbol": "2330", "idx": offset + i} for i in range(2)]
        return httpx.Response(200, json={"rows": rows, "count": 2})

    df = make_client(handler).get_all("twse-daily-price", limit=2)
    assert list(df["idx"]) == [0, 1, 2, 3]
    assert df.attrs["pages_fetched"] == 2


def test_dataset_path_forms_accepted():
    seen = {}

    def handler(request):
        seen.setdefault("paths", []).append(request.url.path)
        return httpx.Response(200, json=ENVELOPE)

    client = make_client(handler)
    client.get_dataset("twse-daily-price")
    client.get_dataset("/v2/datasets/twse-daily-price")
    assert seen["paths"] == ["/v2/datasets/twse-daily-price"] * 2


def test_empty_rows_gives_empty_frame_with_metadata():
    client = make_client(lambda req: httpx.Response(200, json={"rows": [], "count": 0}))
    df = client.get_dataset("twse-daily-price")
    assert df.empty
    assert df.attrs["count"] == 0


def test_repeat_page_guard_survives_null_numeric_columns():
    """Regression: NaN != NaN once broke the ignored-offset guard.

    A partially-null numeric column parses to float64 with NaN. Comparing two
    rows as dicts then reports them unequal even when identical, so the guard
    never fired and the loop refetched page one up to max_pages times.
    """
    calls = {"n": 0}
    payload = {
        "rows": [
            {"symbol": "0000", "close": None, "volume": 100},
            {"symbol": "0000", "close": 100.0, "volume": 200},
        ],
        "count": 2,
    }

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=payload)  # offset ignored

    pages = list(make_client(handler).iter_pages("twse-daily-price", limit=2, max_pages=50))
    assert len(pages) == 1
    assert calls["n"] == 2  # guard fired on the repeat, not 50 requests


class TestRetryAfter:
    def test_delta_seconds_honoured_exactly(self, monkeypatch):
        slept = []
        monkeypatch.setattr(client_mod.time, "sleep", slept.append)
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "7"})
            return httpx.Response(200, json=ENVELOPE)

        make_client(handler).get_dataset("twse-daily-price")
        assert slept == [7.0]  # exact, no jitter, no shortening

    def test_http_date_form_is_parsed(self):
        future = email.utils.format_datetime(
            datetime.now(timezone.utc) + timedelta(seconds=30)
        )
        parsed = client_mod.parse_retry_after(future)
        assert parsed is not None and 25 <= parsed <= 31

    def test_unparseable_value_falls_back_to_backoff(self):
        assert client_mod.parse_retry_after("next tuesday") is None

    def test_excessive_wait_raises_instead_of_retrying_early(self, monkeypatch):
        slept = []
        monkeypatch.setattr(client_mod.time, "sleep", slept.append)
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(
                429,
                json={"error": "rate_limited"},
                headers={"Retry-After": "9999"},
            )

        with pytest.raises(TwmdRateLimitError):
            make_client(handler).get_dataset("twse-daily-price")

        assert slept == []  # never slept
        assert calls["n"] == 1  # and never retried early


class TestItemsEnvelope:
    """The second envelope variant: items/row_count, with nested records."""

    def test_items_records_become_rows(self):
        client = make_client(lambda req: httpx.Response(200, json=ITEMS_ENVELOPE))
        df = client.get_dataset("security-master", ticker="0000")

        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "0000"

    def test_items_envelope_metadata_on_attrs(self):
        client = make_client(lambda req: httpx.Response(200, json=ITEMS_ENVELOPE))
        df = client.get_dataset("security-master", ticker="0000")

        assert df.attrs["dataset_id"] == "security-master"
        assert df.attrs["row_count"] == 1
        assert "items" not in df.attrs

    def test_survivorship_bias_warning_preserved(self):
        """An integrity flag the API raises itself must not be dropped."""
        client = make_client(lambda req: httpx.Response(200, json=ITEMS_ENVELOPE))
        df = client.get_dataset("security-master", ticker="0000")

        warning = df.attrs["survivorship_bias_warning"]
        assert warning["enabled"] is True
        assert warning["level"] == "warning"
        assert "survivorship bias" in warning["message"]

    def test_nested_fields_kept_as_sent(self):
        client = make_client(lambda req: httpx.Response(200, json=ITEMS_ENVELOPE))
        df = client.get_dataset("security-master", ticker="0000")

        assert df.iloc[0]["market_identity"] == {"market": "TWSE"}

    def test_empty_items_gives_empty_frame(self):
        payload = {"dataset_id": "security-master", "row_count": 0, "items": []}
        client = make_client(lambda req: httpx.Response(200, json=payload))
        df = client.get_dataset("security-master", ticker="9999")

        assert df.empty
        assert df.attrs["row_count"] == 0

    def test_pagination_updates_row_count_key(self):
        def handler(request):
            offset = int(request.url.params.get("offset", 0))
            if offset >= 4:
                return httpx.Response(200, json={"items": [], "row_count": 0})
            items = [{"idx": offset + i} for i in range(2)]
            return httpx.Response(200, json={"items": items, "row_count": 2})

        df = make_client(handler).get_all("security-master", limit=2)
        assert list(df["idx"]) == [0, 1, 2, 3]
        assert df.attrs["row_count"] == 4


class TestDataEnvelope:
    """Third observed variant: data / quality.row_count (delisting datasets)."""

    PAYLOAD = {
        "dataset_id": "delisting",
        "request_context": {
            "scope": "twse_delisted_companies_only",
            "coverage_type": "official_complete_list",
            "filters": {"ticker": None, "limit": 2},
            "min_delist_date": "2026-03-27",
            "max_delist_date": "2026-06-23",
        },
        "quality": {"row_count": 1, "ticker_count": 1, "sensitive_fields_exposed": False},
        "lineage": {
            "source_families": ["TWSE_SUSPEND_LISTING"],
            "semantics": "complete official delisting list 2001+",
        },
        "error": None,
        "data": [{"delist_date": "2026-06-23", "ticker": "0000", "market": "TWSE"}],
    }

    def test_data_records_become_rows(self):
        client = make_client(lambda req: httpx.Response(200, json=self.PAYLOAD))
        df = client.get_dataset("delisting", limit=2)

        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "0000"
        assert "data" not in df.attrs

    def test_request_context_and_lineage_preserved(self):
        client = make_client(lambda req: httpx.Response(200, json=self.PAYLOAD))
        df = client.get_dataset("delisting", limit=2)

        assert df.attrs["request_context"]["coverage_type"] == "official_complete_list"
        assert df.attrs["lineage"]["source_families"] == ["TWSE_SUSPEND_LISTING"]
        assert df.attrs["quality"]["row_count"] == 1

    def test_nested_count_is_found(self):
        assert frames.server_count(self.PAYLOAD) == 1

    def test_error_slot_survives(self):
        client = make_client(lambda req: httpx.Response(200, json=self.PAYLOAD))
        df = client.get_dataset("delisting", limit=2)
        assert df.attrs["error"] is None


class TestCatalogFallback:
    """Catalog endpoints name their list after themselves; a fallback finds it."""

    def test_reconciliation_list_is_detected(self):
        payload = {
            "count": 2,
            "reconciliation": [
                {"dataset": "a", "badge": "green"},
                {"dataset": "b", "badge": "amber"},
            ],
            "meta": {"not_investment_advice": True},
        }
        client = make_client(lambda req: httpx.Response(200, json=payload))
        df = client.get_dataset("/v2/data-catalog/reconciliation")

        assert list(df["badge"]) == ["green", "amber"]
        assert df.attrs["meta"]["not_investment_advice"] is True

    def test_metadata_lists_are_not_mistaken_for_records(self):
        """lineage/meta hold lists too; they must not win the fallback."""
        payload = {
            "lineage": {"official_source": ["twse"]},
            "meta": {"market_status": [{"date": "2026-01-01"}]},
            "stats": [{"key": "monthly_revenue", "rows": 331109}],
        }
        assert frames.record_key(payload) == "stats"

    def test_no_list_anywhere_gives_empty_frame(self):
        client = make_client(lambda req: httpx.Response(200, json={"ok": True}))
        df = client.get_dataset("healthz")
        assert df.empty
        assert df.attrs["ok"] is True


class TestAccessMatrix:
    """The measured key-free matrix, per the 2026-07-21 contract probe."""

    def test_sample_dataset_with_sample_ticker(self):
        assert access.is_key_free("twse-daily-price", "2330") is True
        assert access.is_key_free("monthly-revenue", "0050") is True

    def test_sample_dataset_with_other_ticker(self):
        assert access.is_key_free("twse-daily-price", "1101") is False

    def test_open_dataset_any_ticker(self):
        assert access.is_key_free("security-master", "1101") is True
        assert access.is_key_free("market-index") is True

    def test_key_gated_dataset_even_for_sample_ticker(self):
        assert access.is_key_free("institutional-flow", "2330") is False
        assert access.is_key_free("income-statement", "2330") is False

    def test_unknown_dataset_defaults_to_key_required(self):
        assert access.is_key_free("some-future-dataset", "2330") is False

    def test_provenance_separates_measured_from_assumed(self):
        assert access.provenance("twse-daily-price") == "measured"
        assert access.provenance("institutional-flow") == "measured"
        # Declared key-gated in the OpenAPI document but never actually probed.
        assert access.provenance("balance-sheet") == "assumed"
        assert access.provenance("some-future-dataset") == "assumed"

    def test_presumed_and_measured_sets_are_disjoint(self):
        assert not (
            access.KEY_REQUIRED_DATASETS & access.PRESUMED_KEY_REQUIRED_DATASETS
        )
