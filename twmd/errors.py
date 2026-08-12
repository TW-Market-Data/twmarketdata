"""Exception hierarchy.

Error-code classification follows the FRICTION-01 R2 contract (flat
``{"error": "<code>", "message": "..."}`` envelope; 402 for entitlement, 403 for
authenticated-but-forbidden, 429 for quota), plus two cases that contract does
not cover and that the live API does emit:

* ``403 temporarily_blocked`` -- a RATE LIMIT, not an entitlement problem.
  Reading it as "forbidden" sends people hunting for a permissions bug that
  isn't there, so it maps to :class:`RateLimitedError`.
* ``410 endpoint_retired`` -- returned by the retired ``twmarketdata.com``
  gateway. Old code pointed there; the message says where to go instead, so we
  surface it as its own class rather than a generic failure.

Both the flat envelope and the older nested ``{"error": {"code", "message"}}``
shape are parsed, because the two hosts currently disagree.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

__all__ = [
    "TwmdError",
    "TwmdConfigError",
    "FreeTierSymbolError",
    "TwmdAuthError",
    "MissingApiKeyError",
    "InvalidApiKeyError",
    "TierRequiredError",
    "InsufficientCreditsError",
    "TwmdRequestError",
    "DatasetNotFoundError",
    "UnsupportedParameterError",
    "RateLimitedError",
    "EndpointRetiredError",
    "TwmdServerError",
    "PointInTimeUnavailable",
    "NotMappedError",
    # 0.1.0 compatibility aliases
    "TWMarketDataError",
    "AuthenticationError",
    "EntitlementError",
    "RateLimitError",
    "TwmdRateLimitError",
    "UpstreamError",
]


class TwmdError(Exception):
    """Base class for every error raised by this SDK."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        dataset: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id
        self.dataset = dataset
        self.details: Dict[str, Any] = dict(details or {})


# --------------------------------------------------------------------------- config
class TwmdConfigError(TwmdError):
    """The SDK was configured in a way that cannot work."""


class FreeTierSymbolError(TwmdConfigError):
    """A non-demo symbol was requested without an API key."""

    def __init__(self, ticker: str, allowed: Sequence[str]) -> None:
        self.ticker = ticker
        self.allowed = list(allowed)
        super().__init__(
            "No API key configured, so only the free-tier demo symbols are available. "
            "Requested %r; allowed: %s. Pass an API key (Client(api_key=...) or the "
            "TWMD_API_KEY environment variable) to query any symbol."
            % (ticker, ", ".join(allowed))
        )


# --------------------------------------------------------------------------- auth
class TwmdAuthError(TwmdError):
    """Authentication or entitlement failure."""


class MissingApiKeyError(TwmdAuthError):
    """401 missing_api_key -- this dataset needs a key and none was sent."""


class InvalidApiKeyError(TwmdAuthError):
    """401 invalid_api_key / 403 api_key_revoked / api_key_not_active."""


class TierRequiredError(TwmdAuthError):
    """The key authenticated but the plan does not include this dataset."""

    def __init__(self, message: str, *, required_tier: Optional[str] = None, **kw: Any) -> None:
        super().__init__(message, **kw)
        self.required_tier = required_tier


class InsufficientCreditsError(TwmdAuthError):
    """402 insufficient_credits."""


# --------------------------------------------------------------------------- request
class TwmdRequestError(TwmdError):
    """The request itself was wrong."""


class DatasetNotFoundError(TwmdRequestError):
    """Unknown dataset key, or 404 from the API."""


class UnsupportedParameterError(TwmdRequestError):
    """A parameter was passed that this dataset's route does not accept.

    Deliberately an error and not a silent drop: quietly ignoring ``start=`` on a
    dataset with no date parameter would return a full unfiltered history that
    looks like a filtered one.
    """

    def __init__(self, dataset: str, parameter: str, supported: Sequence[str]) -> None:
        self.parameter = parameter
        self.supported = list(supported)
        super().__init__(
            "Dataset %r does not accept %r. It accepts: %s. "
            "See twmd.capabilities(%r) for what this dataset supports."
            % (dataset, parameter, ", ".join(supported) or "(no filters)", dataset),
            dataset=dataset,
        )


# --------------------------------------------------------------------------- transport
class RateLimitedError(TwmdError):
    """429, or 403 temporarily_blocked.

    The 403 form is a rate limit despite the status code. The message says so
    explicitly so nobody goes looking for a permissions problem.
    """

    def __init__(self, message: str, *, retry_after: Optional[float] = None, **kw: Any) -> None:
        super().__init__(message, **kw)
        self.retry_after = retry_after


class EndpointRetiredError(TwmdError):
    """410 endpoint_retired -- the host being called has been decommissioned."""


class TwmdServerError(TwmdError):
    """5xx, upstream_error, upstream_timeout, or a transport failure."""


# --------------------------------------------------------------------------- semantics
class PointInTimeUnavailable(TwmdError):
    """``as_of`` cannot be honoured for this dataset.

    Raised rather than answered, because the alternative is handing back a frame
    that looks like a point-in-time replay but is not one.
    """

    def __init__(self, dataset: str, reason: str) -> None:
        self.reason = reason
        super().__init__(
            "as_of is not available for dataset %r: %s" % (dataset, reason),
            dataset=dataset,
        )


class NotMappedError(TwmdError):
    """A compat-layer call has no TWMD equivalent.

    Raised instead of returning an empty frame, so "no mapping exists" can never
    be mistaken for "the query found nothing".
    """

    def __init__(self, call: str, reason: str, *, suggestion: Optional[str] = None) -> None:
        self.call = call
        self.reason = reason
        self.suggestion = suggestion
        text = "%s has no TW Market Data equivalent: %s" % (call, reason)
        if suggestion:
            text += " Closest available: %s" % suggestion
        super().__init__(text)


# --------------------------------------------------------------------------- classification
_ENTITLEMENT_CODES = frozenset({
    "not_entitled_for_dataset", "dataset_not_entitled", "commercial_use_not_allowed",
    "plan_not_entitled", "dataset_not_allowed", "mcp_not_in_plan",
})
_KEY_INVALID_CODES = frozenset({"invalid_api_key", "api_key_revoked", "api_key_not_active"})
_QUOTA_CODES = frozenset({"rate_limit_exceeded", "daily_quota_exceeded", "monthly_quota_exceeded"})
_UPSTREAM_CODES = frozenset({"upstream_error", "upstream_timeout"})


def classify(
    status_code: int,
    error_code: Optional[str],
    message: str,
    *,
    request_id: Optional[str] = None,
    dataset: Optional[str] = None,
    retry_after: Optional[float] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> TwmdError:
    """Map an HTTP status plus an API error code onto an exception instance."""
    kw: Dict[str, Any] = {
        "status_code": status_code,
        "error_code": error_code,
        "request_id": request_id,
        "dataset": dataset,
        "details": dict(details or {}),
    }

    if error_code == "temporarily_blocked":
        return RateLimitedError(
            "Rate limited by the API (403 temporarily_blocked). This is a rate limit, "
            "not a permissions problem: lower max_concurrency or retry after a pause. "
            "Original message: %s" % message,
            retry_after=retry_after, **kw,
        )
    if status_code == 410 or error_code == "endpoint_retired":
        return EndpointRetiredError(
            "The endpoint being called has been retired. %s "
            "The current base URL is https://api.twmarketdata.com/v2 ." % message, **kw)
    if error_code == "missing_api_key" or (status_code == 401 and not error_code):
        return MissingApiKeyError(message, **kw)
    if error_code in _KEY_INVALID_CODES:
        return InvalidApiKeyError(message, **kw)
    if status_code == 401:
        return MissingApiKeyError(message, **kw)
    # Classify entitlement by CODE before the generic 402 = credits branch.
    if error_code in _ENTITLEMENT_CODES:
        return TierRequiredError(message, **kw)
    if status_code == 402 or error_code == "insufficient_credits":
        return InsufficientCreditsError(message, **kw)
    if status_code == 403:
        return TierRequiredError(message, **kw)
    if status_code == 404 or error_code == "dataset_not_found":
        return DatasetNotFoundError(message, **kw)
    if status_code == 429 or error_code in _QUOTA_CODES:
        return RateLimitedError(message, retry_after=retry_after, **kw)
    if status_code >= 500 or error_code in _UPSTREAM_CODES:
        return TwmdServerError(message, **kw)
    return TwmdError(message, **kw)


# --------------------------------------------------------------------------- 0.1.0 aliases
# The 0.1.0 preview SDK used these names. Kept so existing imports resolve.
TWMarketDataError = TwmdError
AuthenticationError = TwmdAuthError
EntitlementError = TierRequiredError
RateLimitError = RateLimitedError
TwmdRateLimitError = RateLimitedError   # 0.1.0 spelling
UpstreamError = TwmdServerError
