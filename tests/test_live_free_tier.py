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


def test_monthly_revenue_knowledge_date_is_live_and_imputed(client):
    """WORKORDER_API_expose_knowledge_date phase 1, as deployed for this dataset.

    Shipped for monthly_revenue on 2026-08-12. If knowledge_date ever disappears
    from this response, this fails loudly rather than quietly reverting to the
    refusal path -- a rollback on the API side is something we want to hear about.
    """
    from twmd.envelope import extract_rows
    extracted, _ = extract_rows(
        client.dataset("monthly_revenue", ticker="2330", limit=3, raw=True))
    assert extracted, "no rows returned for 2330"
    assert all("knowledge_date" in r for r in extracted), \
        "knowledge_date vanished from monthly_revenue; the API rolled back"
    assert all(r.get("kd_source") == "statutory_deadline" for r in extracted)


def test_monthly_revenue_as_of_filters_via_server_knowledge_date(client):
    """The registry calls this dataset unsafe; the server's column overrides that.

    June revenue carries knowledge_date 2026-07-10, so an as_of of 2026-06-30
    must drop it. That single row is the look-ahead the mechanism exists for.
    """
    with pytest.warns(twmd.ImputedKnowledgeDateWarning):
        df = client.dataset("monthly_revenue", ticker="2330", as_of="2026-06-30")

    meta = client.last_meta
    assert meta.as_of_applied is True
    assert meta.as_of_field == "knowledge_date"
    # Every row the API returned was imputed, and at least one was filtered out.
    assert meta.knowledge_date_imputed_rows > len(df)
    assert meta.knowledge_date_sources == ["statutory_deadline"]
    assert len(df) > 0
    assert max(df["knowledge_date"]) <= "2026-06-30"


def test_a_dataset_with_no_knowledge_axis_still_refuses_without_a_request(client):
    with pytest.raises(twmd.PointInTimeUnavailable):
        client.dataset("company_peer_groups", as_of="2026-06-30")


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
