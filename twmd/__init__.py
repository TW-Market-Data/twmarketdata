"""TW Market Data (TWMD) Python SDK.

TWMD = TW Market Data = https://twmarketdata.com

Two lines to data, no API key needed for the demo symbols::

    from twmd import Client
    df = Client().daily_price("2330")

What this SDK adds on top of the REST API:

* **One shape for 82 datasets.** Entity parameters come in seven spellings on
  the live API and date parameters in five; here they are always ``ticker``,
  ``start``, ``end``.
* **Point-in-time you can trust.** ``as_of=`` replays a dataset to what was
  knowable on a date -- and *refuses* on the datasets where an honest replay is
  not possible, instead of returning a frame that merely looks replayed.
  Imputed knowledge dates are flagged as imputed.
* **Gaps surfaced, never filled.** Missing data is reported with its source
  (``server`` / ``client_derived`` / ``unknown``). Nothing is zero-filled,
  forward-filled or interpolated.
* **Truncation is visible.** Only 9 of 82 routes paginate; when a result is cut
  off, ``Meta.truncated`` says so.

Start with :func:`capabilities` to see what a dataset supports before querying::

    import twmd
    twmd.capabilities("monthly_revenue")
"""
from __future__ import annotations

from .client import Client, TWMarketDataClient
from .errors import (AuthenticationError, DatasetNotFoundError, EndpointRetiredError,
                     EntitlementError, FreeTierSymbolError, InsufficientCreditsError,
                     InvalidApiKeyError, MissingApiKeyError, NotMappedError,
                     PointInTimeUnavailable, RateLimitedError, RateLimitError,
                     TierRequiredError, TWMarketDataError, TwmdAuthError, TwmdConfigError,
                     TwmdRateLimitError,
                     TwmdError, TwmdRequestError, TwmdServerError,
                     UnsupportedParameterError, UpstreamError, ValidationError)
from . import access, frames  # noqa: F401  (0.1.0 module layout)
from ._legacy import (API_KEY_ENV, KEY_REQUIRED, KEY_REQUIRED_DATASETS, OPEN,
                      OPEN_DATASETS, PRESUMED_KEY_REQUIRED_DATASETS, SAMPLE,
                      SAMPLE_DATASETS, SAMPLE_TICKERS, TwmdAPIError,
                      TwmdNotFoundError, TwmdPaymentRequired, TwmdTransportError,
                      TwmdValidationError, access_tier, concat_frames, explain,
                      is_key_free, provenance, record_key, server_count, to_dataframe)
from .frame import TwmdFrame, pandas_available
from .meta import (CompatSubstitutionWarning, DatasetStatusWarning, Gap,
                   ImputedKnowledgeDateWarning, Meta, PITDataMissingWarning,
                   TruncatedPointInTimeWarning, TruncatedResultWarning, TwmdWarning)
from .registry import (DEFAULT_BASE_URL, REGISTRY_MEASURED_ON, DatasetInfo,
                       capabilities, datasets, free_tier_symbols, get,
                       runnable_without_key)

__version__ = "0.4.0"

__all__ = [
    "__version__",
    # client
    "Client", "TWMarketDataClient",
    # registry
    "datasets", "capabilities", "get", "DatasetInfo", "free_tier_symbols",
    "runnable_without_key", "REGISTRY_MEASURED_ON", "DEFAULT_BASE_URL",
    # response
    "TwmdFrame", "Meta", "Gap", "pandas_available",
    # warnings
    "TwmdWarning", "PITDataMissingWarning", "ImputedKnowledgeDateWarning",
    "TruncatedPointInTimeWarning", "TruncatedResultWarning",
    "CompatSubstitutionWarning", "DatasetStatusWarning",
    # errors
    "TwmdError", "TwmdConfigError", "FreeTierSymbolError", "TwmdAuthError",
    "MissingApiKeyError", "InvalidApiKeyError", "TierRequiredError",
    "InsufficientCreditsError", "TwmdRequestError", "DatasetNotFoundError",
    "UnsupportedParameterError", "ValidationError", "RateLimitedError", "EndpointRetiredError",
    "TwmdServerError", "PointInTimeUnavailable", "NotMappedError",
    # --- 0.1.0 compatibility surface (deprecated, still working) ---
    "TWMarketDataError", "AuthenticationError", "EntitlementError",
    "RateLimitError", "UpstreamError",
    "TwmdAPIError", "TwmdTransportError", "TwmdNotFoundError", "TwmdRateLimitError",
    "TwmdValidationError", "TwmdPaymentRequired",
    "access", "frames", "API_KEY_ENV",
    "SAMPLE_TICKERS", "OPEN_DATASETS", "SAMPLE_DATASETS", "KEY_REQUIRED_DATASETS",
    "PRESUMED_KEY_REQUIRED_DATASETS", "OPEN", "SAMPLE", "KEY_REQUIRED",
    "access_tier", "provenance", "is_key_free", "explain",
    "to_dataframe", "record_key", "server_count", "concat_frames",
]
