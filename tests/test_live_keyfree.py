"""Live acceptance: the five sample tickers must work with zero configuration.

Network tests. Run with ``pytest -m live``; excluded by default in CI sandboxes
that have no egress.
"""

from __future__ import annotations

import os

import pytest

from twmd import Client, SAMPLE_TICKERS
from twmd.errors import TwmdAuthError

pytestmark = pytest.mark.live


@pytest.fixture()
def keyfree_client(monkeypatch):
    """A client that carries no key, even if the shell exports one."""
    monkeypatch.delenv("TWMD_API_KEY", raising=False)
    with Client() as client:
        assert client.has_api_key is False
        yield client


@pytest.mark.parametrize("symbol", sorted(SAMPLE_TICKERS))
def test_sample_tickers_return_data_without_a_key(keyfree_client, symbol):
    df = keyfree_client.get_dataset("twse-daily-price", symbol=symbol, limit=2)

    assert not df.empty
    assert set(df["symbol"]) == {symbol}
    assert {"date", "open", "high", "low", "close"} <= set(df.columns)
    assert df["close"].notna().all()


def test_envelope_metadata_present(keyfree_client):
    df = keyfree_client.get_dataset("twse-daily-price", symbol="2330", limit=1)

    assert df.attrs["dataset"] == "twse_daily_price"
    assert df.attrs["data_as_of"]
    assert df.attrs["lineage"]["provider"] == "TWSE"
    assert df.attrs["lineage"]["not_investment_advice"] is True


def test_monthly_revenue_is_key_free_for_sample_tickers(keyfree_client):
    df = keyfree_client.get_dataset("monthly-revenue", symbol="2330", limit=2)
    assert not df.empty
    assert "revenue" in df.columns


def test_open_dataset_serves_non_sample_ticker(keyfree_client):
    """security-master is open to any ticker, and uses the items/row_count envelope."""
    df = keyfree_client.get_dataset("security-master", ticker="1101", limit=1)

    assert not df.empty
    assert df.iloc[0]["ticker"] == "1101"
    assert df.attrs["dataset_id"] == "security-master"
    # The API raises this integrity caveat itself; it must reach the caller.
    assert df.attrs["survivorship_bias_warning"]["enabled"] is True


def test_market_index_is_open(keyfree_client):
    df = keyfree_client.get_dataset("market-index", limit=1)
    assert not df.empty
    assert df.attrs["dataset_id"] == "market-index"


def test_non_sample_ticker_on_sample_dataset_is_rejected(keyfree_client):
    with pytest.raises(TwmdAuthError) as info:
        keyfree_client.get_dataset("twse-daily-price", symbol="1101", limit=1)
    assert info.value.error_code == "missing_api_key"


def test_key_gated_dataset_rejects_even_sample_ticker(keyfree_client):
    with pytest.raises(TwmdAuthError) as info:
        keyfree_client.get_dataset("institutional-flow", symbol="2330", limit=1)
    assert info.value.error_code == "missing_api_key"


def test_access_matrix_matches_live_api(keyfree_client):
    """The declared matrix must not drift from what the API actually serves."""
    cases = [
        ("twse-daily-price", "symbol", "2330", True),
        ("tpex-daily-price", "symbol", "2330", True),
        ("monthly-revenue", "symbol", "2330", True),
        ("security-master", "ticker", "1101", True),
        ("twse-daily-price", "symbol", "1101", False),
        ("institutional-flow", "symbol", "2330", False),
        ("market-breadth", "symbol", "2330", False),
    ]
    for dataset, param, ticker, expected in cases:
        assert keyfree_client.is_key_free(dataset, ticker) is expected, dataset
        try:
            keyfree_client.get_dataset(dataset, limit=1, **{param: ticker})
            reachable = True
        except TwmdAuthError:
            reachable = False
        assert reachable is expected, f"{dataset}/{ticker} drifted from the matrix"


@pytest.mark.skipif(
    not os.environ.get("TWMD_API_KEY"),
    reason="no key available; owner verifies the entitled path separately",
)
def test_key_gated_dataset_with_key():
    with Client() as client:
        df = client.get_dataset("institutional-flow", symbol="2330", limit=1)
        assert not df.empty
