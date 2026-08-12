"""Envelope normalisation and error classification.

The API returns rows under three different keys and errors in two different
shapes. Both are exercised here with the exact payloads observed on 2026-08-12.
"""
from __future__ import annotations

import pytest

from twmd.envelope import extract_count, extract_error, extract_gaps, extract_rows
from twmd.errors import (DatasetNotFoundError, EndpointRetiredError, InsufficientCreditsError,
                         InvalidApiKeyError, MissingApiKeyError, RateLimitedError,
                         TierRequiredError, TwmdServerError, classify)


# --------------------------------------------------------------------- rows
@pytest.mark.parametrize("key", ["rows", "items", "data", "results", "records"])
def test_rows_found_under_every_observed_key(key):
    rows, found = extract_rows({"dataset": "x", key: [{"a": 1}]})
    assert rows == [{"a": 1}]
    assert found == key


def test_row_key_precedence_is_deterministic():
    rows, key = extract_rows({"rows": [{"a": 1}], "data": [{"b": 2}]})
    assert key == "rows" and rows == [{"a": 1}]


def test_no_array_is_not_an_error_it_is_no_rows():
    assert extract_rows({"dataset": "x", "count": 0}) == ([], None)


def test_count_key_variants():
    assert extract_count({"count": 7}, 0) == 7
    assert extract_count({"row_count": 8}, 0) == 8
    assert extract_count({"data_count": 9}, 0) == 9
    assert extract_count({}, 3) == 3


# --------------------------------------------------------------------- gaps
def test_absent_gaps_is_unknown_not_empty():
    # None means "the server said nothing"; [] would mean "the server said none".
    assert extract_gaps({"rows": []}) is None
    assert extract_gaps({"rows": [], "known_gaps": []}) == []


def test_gap_objects_parsed():
    gaps = extract_gaps({"data_gaps": [{"start": "2024-01-02", "end": "2024-01-05",
                                        "reason": "source_not_published"}]})
    assert len(gaps) == 1
    assert gaps[0].start == "2024-01-02" and gaps[0].reason == "source_not_published"


# -------------------------------------------------------------------- errors
def test_flat_error_envelope_from_live_api():
    # Exactly what api.twmarketdata.com returns for a key-less paid dataset.
    code, message = extract_error(
        {"error": "missing_api_key",
         "message": "缺少 API 金鑰。請在 X-API-KEY 標頭帶入金鑰,或改打五檔免金鑰試玩端點。"}, 401)
    assert code == "missing_api_key"
    assert "X-API-KEY" in message  # server wording survives


def test_nested_error_envelope_from_retired_gateway():
    code, message = extract_error(
        {"error": {"code": "endpoint_retired", "message": "This gateway is retired."}}, 410)
    assert code == "endpoint_retired"
    assert message == "This gateway is retired."


def test_unparseable_error_still_gets_a_message():
    code, message = extract_error(None, 500)
    assert code is None and "500" in message


# ------------------------------------------------------------ classification
def test_403_temporarily_blocked_is_a_rate_limit_not_a_permission_problem():
    err = classify(403, "temporarily_blocked", "blocked")
    assert isinstance(err, RateLimitedError)
    assert not isinstance(err, TierRequiredError)
    assert "not a permissions problem" in str(err)


def test_410_endpoint_retired_points_at_the_live_base_url():
    err = classify(410, "endpoint_retired", "This gateway is retired.")
    assert isinstance(err, EndpointRetiredError)
    assert "api.twmarketdata.com/v2" in str(err)


@pytest.mark.parametrize("code", [
    "not_entitled_for_dataset", "dataset_not_entitled", "commercial_use_not_allowed",
])
def test_402_entitlement_codes_beat_the_generic_credits_branch(code):
    # FRICTION-01 R2: paywall moved to 402, so code must be checked before status.
    err = classify(402, code, "not entitled")
    assert isinstance(err, TierRequiredError)
    assert not isinstance(err, InsufficientCreditsError)


def test_402_without_an_entitlement_code_is_credits():
    assert isinstance(classify(402, "insufficient_credits", "no credits"),
                      InsufficientCreditsError)


@pytest.mark.parametrize("code", ["api_key_revoked", "api_key_not_active", "invalid_api_key"])
def test_key_problems_are_distinct_from_plan_problems(code):
    assert isinstance(classify(403, code, "bad key"), InvalidApiKeyError)


@pytest.mark.parametrize("code", ["daily_quota_exceeded", "monthly_quota_exceeded"])
def test_quota_codes_are_rate_limits(code):
    assert isinstance(classify(429, code, "quota"), RateLimitedError)


def test_missing_key_and_404_and_5xx():
    assert isinstance(classify(401, "missing_api_key", "no key"), MissingApiKeyError)
    assert isinstance(classify(404, "dataset_not_found", "nope"), DatasetNotFoundError)
    assert isinstance(classify(503, None, "down"), TwmdServerError)
