"""twmd — data-access client for the TW Market Data API.

Fetches published datasets and returns them as pandas DataFrames, for research
and educational use. This package is a retrieval layer only: it transports
records as the API sends them and adds no analysis or interpretation.
"""

from __future__ import annotations

from .access import (
    KEY_REQUIRED_DATASETS,
    OPEN_DATASETS,
    PRESUMED_KEY_REQUIRED_DATASETS,
    SAMPLE_DATASETS,
    SAMPLE_TICKERS,
    access_tier,
    explain,
    is_key_free,
    provenance,
)
from .client import API_KEY_ENV, DEFAULT_BASE_URL, Client
from .errors import (
    TwmdAPIError,
    TwmdAuthError,
    TwmdConfigError,
    TwmdError,
    TwmdNotFoundError,
    TwmdPaymentRequired,
    TwmdRateLimitError,
    TwmdServerError,
    TwmdTransportError,
    TwmdValidationError,
)
from .frames import to_dataframe

__version__ = "0.1.0"

__all__ = [
    "Client",
    "API_KEY_ENV",
    "DEFAULT_BASE_URL",
    "SAMPLE_TICKERS",
    "OPEN_DATASETS",
    "SAMPLE_DATASETS",
    "KEY_REQUIRED_DATASETS",
    "PRESUMED_KEY_REQUIRED_DATASETS",
    "access_tier",
    "is_key_free",
    "explain",
    "provenance",
    "to_dataframe",
    "TwmdError",
    "TwmdConfigError",
    "TwmdTransportError",
    "TwmdAPIError",
    "TwmdAuthError",
    "TwmdPaymentRequired",
    "TwmdNotFoundError",
    "TwmdValidationError",
    "TwmdRateLimitError",
    "TwmdServerError",
    "__version__",
]
