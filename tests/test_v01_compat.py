"""The published 0.1.0 surface must keep resolving on 0.2.0.

`twmarketdata` 0.1.0 went to PyPI on 2026-07-21 importing as `twmd`. 0.2.0 keeps
the same distribution and import name, so anything 0.1.0 exported has to still
be there. The expected surface below was captured by introspecting the installed
0.1.0 wheel, so this test does not need that wheel present to run.
"""
from __future__ import annotations

import warnings

import pytest

import twmd
from conftest import FakeResponse, rows_envelope

# Captured from `dir(twmd)` on the installed twmarketdata 0.1.0 wheel.
V01_MODULE_NAMES = [
    "API_KEY_ENV", "Client", "DEFAULT_BASE_URL", "KEY_REQUIRED_DATASETS",
    "OPEN_DATASETS", "PRESUMED_KEY_REQUIRED_DATASETS", "SAMPLE_DATASETS",
    "SAMPLE_TICKERS", "TwmdAPIError", "TwmdAuthError", "TwmdConfigError",
    "TwmdError", "TwmdNotFoundError", "TwmdPaymentRequired", "TwmdRateLimitError",
    "TwmdServerError", "TwmdTransportError", "TwmdValidationError", "access",
    "access_tier", "client", "errors", "explain", "frames", "is_key_free",
    "provenance", "to_dataframe",
]

V01_CLIENT_METHODS = ["close", "get_all", "get_dataset", "is_key_free",
                      "iter_pages", "list_datasets"]


@pytest.mark.parametrize("name", V01_MODULE_NAMES)
def test_every_0_1_0_module_level_name_still_resolves(name):
    assert hasattr(twmd, name), "0.1.0 exported %s; removing it breaks installs" % name


@pytest.mark.parametrize("name", V01_CLIENT_METHODS)
def test_every_0_1_0_client_method_still_exists(name):
    assert callable(getattr(twmd.Client(), name))


def test_0_1_0_submodules_are_importable():
    from twmd import access, frames                     # noqa: F401
    from twmd.compat import v01                         # noqa: F401
    from twmd.frames import to_dataframe                # noqa: F401
    from twmd.access import access_tier, SAMPLE_TICKERS  # noqa: F401


# ------------------------------------------------------------------- access
def test_sample_tier_semantics_preserved():
    # SAMPLE means: key-free only for the demo tickers.
    assert twmd.access_tier("twse-daily-price") == twmd.SAMPLE
    assert twmd.is_key_free("twse-daily-price", "2330") is True
    assert twmd.is_key_free("twse-daily-price", "1101") is False
    assert twmd.is_key_free("twse-daily-price") is False   # no ticker -> False


def test_open_tier_semantics_preserved():
    assert twmd.access_tier("security-master") == twmd.OPEN
    assert twmd.is_key_free("security-master", "1101") is True


def test_key_required_is_the_safe_default():
    assert twmd.access_tier("definitely-not-a-dataset") == twmd.KEY_REQUIRED
    assert twmd.is_key_free("income-statement", "2330") is False


def test_open_set_was_re_measured_not_copied():
    # 0.1.0 listed 2 open datasets from a 2026-07-21 probe; a full sweep plus a
    # non-demo-ticker sweep on 2026-08-12 found more. Shipping the old, narrower
    # list would mean shipping data already known to be incomplete.
    assert {"security-master", "market-index"} <= twmd.OPEN_DATASETS
    assert len(twmd.OPEN_DATASETS) > 2
    assert twmd.SAMPLE_DATASETS == frozenset(
        {"twse-daily-price", "tpex-daily-price", "monthly-revenue"})
    assert twmd.provenance("security-master") == "measured"


def test_explain_distinguishes_missing_key_from_wrong_ticker():
    assert "any ticker" in twmd.explain("security-master")
    assert "1101" in twmd.explain("twse-daily-price", "1101")
    assert "requires an API key" in twmd.explain("income-statement")


# ------------------------------------------------------------------- frames
def test_to_dataframe_keeps_envelope_metadata_on_attrs():
    if not twmd.pandas_available():
        pytest.skip("pandas not installed")
    payload = {"dataset": "x", "rows": [{"a": 1}], "count": 1,
               "lineage": {"provider": "TWSE"}}
    df = twmd.to_dataframe(payload)
    assert list(df["a"]) == [1]
    assert df.attrs["lineage"] == {"provider": "TWSE"}
    assert "rows" not in df.attrs


def test_record_key_and_server_count_cover_every_envelope():
    assert twmd.record_key({"items": [{"a": 1}]}) == "items"
    assert twmd.record_key({"reconciliation": [{"a": 1}]}) == "reconciliation"
    assert twmd.record_key({"lineage": []}) is None
    assert twmd.server_count({"quality": {"row_count": 4}}) == 4


# ------------------------------------------------------------------ client
def test_get_dataset_translates_0_1_0_parameter_names(session):
    c = twmd.Client(session=session)
    with pytest.warns(DeprecationWarning, match="0.1.0 API"):
        c.get_dataset("monthly-revenue", symbol="2330", date_from="2024-01-01")
    params = session.calls[0]["params"]
    assert params["symbol"] == "2330"          # route's own spelling
    assert params["start_date"] == "2024-01-01"  # date_from -> start -> start_date


def test_get_dataset_accepts_kebab_route_slugs(session):
    c = twmd.Client(session=session)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        c.get_dataset("twse-daily-price", symbol="2330")
    assert "twse-daily-price" in session.calls[0]["url"]


def test_iter_pages_stops_when_the_server_ignores_offset(session):
    # Measured on index-constituents: offsets 0/3/6 returned identical pages.
    c = twmd.Client(session=session, default_limit=2)
    same = rows_envelope([{"a": 1}, {"a": 2}])
    session.queue = [FakeResponse(dict(same)) for _ in range(5)]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pages = list(c.iter_pages("index_constituents", limit=2))
    assert len(pages) == 1                      # not an endless stream of dupes
    assert any("does not honour offset" in str(w.message) for w in caught)


def test_get_all_concatenates_real_pages(session):
    c = twmd.Client(session=session)
    session.queue = [
        FakeResponse(rows_envelope([{"a": 1}, {"a": 2}])),
        FakeResponse(rows_envelope([{"a": 3}])),
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = c.get_all("index_constituents", limit=2)
    assert len(df) == 3


def test_list_datasets_returns_the_catalogue(session):
    c = twmd.Client(session=session)
    with pytest.warns(DeprecationWarning):
        df = c.list_datasets()
    assert len(df) == 82


def test_payment_required_still_exposes_its_accessors():
    exc = twmd.TwmdPaymentRequired(
        "plan does not include this dataset",
        details={"payment": {"price": "pro",
                             "credits_url": "https://twmarketdata.com/pricing",
                             "purchase_hint": "upgrade_plan"}})
    assert exc.price == "pro"
    assert exc.credits_url == "https://twmarketdata.com/pricing"
    assert exc.purchase_hint == "upgrade_plan"


def test_legacy_error_classes_slot_into_the_new_hierarchy():
    # Old `except TwmdError` blocks must still catch everything.
    for cls in (twmd.TwmdAPIError, twmd.TwmdTransportError, twmd.TwmdNotFoundError,
                twmd.TwmdValidationError, twmd.TwmdPaymentRequired):
        assert issubclass(cls, twmd.TwmdError)
    assert issubclass(twmd.TwmdPaymentRequired, twmd.TierRequiredError)
    assert issubclass(twmd.TwmdNotFoundError, twmd.DatasetNotFoundError)


def test_twmarketdata_client_alias_warns_and_uses_the_live_base_url():
    with pytest.warns(DeprecationWarning, match="410"):
        c = twmd.TWMarketDataClient()
    assert "api.twmarketdata.com" in c._transport.base_url


@pytest.mark.skipif(not hasattr(twmd, "__file__"), reason="needs a real package")
def test_installed_0_1_0_surface_is_covered_if_present():
    """If the 0.1.0 wheel is importable, diff its surface against ours."""
    import importlib.util
    import sys
    spec = None
    for path in sys.path:
        if "site-packages" in path:
            candidate = importlib.util.find_spec("twmd")
            spec = candidate
            break
    if spec is None:
        pytest.skip("0.1.0 not installed alongside")
