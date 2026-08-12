"""Live checks against the real API, free tier, no key required.

Run with ``pytest -m network``. Skipped by default so the offline suite stays
fast and hermetic.

Deliberately paced: probing the API too fast returns ``403 temporarily_blocked``
and the block persists for a while, so these tests sleep between calls and cover
a representative subset rather than hammering all 82 routes. Nothing here needs
an API key, which is the point -- CI can run it.
"""
from __future__ import annotations

import os
import time

import pytest

import twmd

pytestmark = pytest.mark.network

PACE_SECONDS = 2.0

# A representative slice of the datasets measured to return rows without a key:
# one daily price series, one monthly fundamental, two dimension tables.
LIVE_DATASETS = ["twse_daily_price", "monthly_revenue", "security_master", "trading_calendar"]


@pytest.fixture(scope="module")
def client():
    c = twmd.Client(max_concurrency=1)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _pace():
    yield
    time.sleep(PACE_SECONDS)


@pytest.mark.parametrize("dataset", LIVE_DATASETS)
def test_free_tier_dataset_returns_rows(client, dataset):
    assert twmd.get(dataset).runnable_without_key, "registry says this needs a key"
    kwargs = {"limit": 3}
    if twmd.get(dataset).entity_param:
        kwargs["ticker"] = "2330"
    df = client.dataset(dataset, **kwargs)
    assert len(df) > 0
    meta = client.last_meta
    assert meta.status_code == 200
    assert meta.row_key in {"rows", "items", "data"}


def test_two_line_quickstart_works(client):
    """The README promise: two lines, no key, real data for 2330."""
    df = client.daily_price("2330", limit=5)
    assert len(df) > 0
    assert "market" in df.columns
    assert {"TWSE"} <= set(df["market"])


def test_paid_dataset_gives_a_clear_key_error(client):
    with pytest.raises(twmd.MissingApiKeyError) as exc:
        client.dataset("income_statement", ticker="2330", limit=1)
    # The server's own wording survives our error handling.
    assert exc.value.error_code == "missing_api_key"
    assert "API" in str(exc.value)


def test_free_tier_symbol_guard_is_enforced_before_the_request(client):
    with pytest.raises(twmd.FreeTierSymbolError):
        client.dataset("monthly_revenue", ticker="1101")


def test_declared_free_but_actually_gated_dataset_still_401s(client):
    # Appendix K: valuation_data is tier=free yet returns 401. If this starts
    # passing, the registry's free_tier_probe column needs regenerating.
    assert twmd.get("valuation_data").tier == "free"
    with pytest.raises(twmd.MissingApiKeyError):
        client.dataset("valuation_data", ticker="2330", limit=1)


def test_monthly_revenue_knowledge_columns_reflect_production(client):
    """Tracks WORKORDER_API_expose_knowledge_date rollout.

    Before Phase 1 ships, the response has no knowledge_date and the SDK must
    refuse as_of by default. After it ships, knowledge_date appears and as_of
    starts working with an imputed-date warning. Either way the SDK is honest;
    this test records which world we are in.
    """
    rows = client.dataset("monthly_revenue", ticker="2330", limit=3, raw=True)
    from twmd.envelope import extract_rows
    extracted, _ = extract_rows(rows)
    assert extracted, "no rows returned for 2330"

    has_kd = any("knowledge_date" in r for r in extracted)
    if not has_kd:
        with pytest.raises(twmd.PointInTimeUnavailable):
            client.dataset("monthly_revenue", ticker="2330", as_of="2026-06-30")
    else:
        with pytest.warns(twmd.ImputedKnowledgeDateWarning):
            client.dataset("monthly_revenue", ticker="2330", as_of="2026-06-30")


@pytest.mark.skipif(not os.environ.get("TWMD_LIVE_ALL"),
                    reason="set TWMD_LIVE_ALL=1 to sweep every free-tier dataset")
@pytest.mark.parametrize("dataset", twmd.runnable_without_key())
def test_every_free_tier_dataset(client, dataset):
    info = twmd.get(dataset)
    kwargs = {"limit": 2}
    if info.entity_param:
        kwargs["ticker"] = "2330"
    client.dataset(dataset, **kwargs)
    assert client.last_meta.status_code == 200
