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

def _installed_version() -> str:
    """版本的**單一真相源**:已安裝套件的 metadata(也就是 pyproject 的 version)。

    ⚠️ 這裡原本是一個硬編碼字串,而它**必然**會和 pyproject 漂移 —— 而且已經漂了:
    發 v0.6.0 時 pyproject 更新了,這一行沒有,於是 `twmd --version` 對外說 0.5.0
    而使用者裝到的是 0.6.0。

    版本漂移的症狀特別惡劣:回報 bug 的人會附上 `twmd --version` 的輸出,
    而那個數字是**錯的** —— 於是查的人去看一個他根本沒在跑的版本的程式碼。

    ⚠️ 從原始碼樹直接跑(沒有 pip install)時 metadata 不存在。那時候回
    `0.0.0+unknown` 而**不是**猜一個版本號:一個猜出來的版本號和真的長得一樣,
    而它會被貼進工單裡。
    """
    from importlib import metadata  # noqa: PLC0415

    try:
        return metadata.version("twmarketdata")
    except Exception:  # noqa: BLE001 - PackageNotFoundError 以及任何 metadata 損壞
        return "0.0.0+unknown"


__version__ = _installed_version()

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
