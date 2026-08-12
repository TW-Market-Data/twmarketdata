"""0.1.0's ``twmd.access`` module, kept so existing imports resolve.

The access tables were re-measured on 2026-08-12; see :mod:`twmd._legacy`.
Prefer :func:`twmd.runnable_without_key` and :func:`twmd.capabilities`.
"""
from __future__ import annotations

from ._legacy import (KEY_REQUIRED, KEY_REQUIRED_DATASETS, OPEN, OPEN_DATASETS,
                      PRESUMED_KEY_REQUIRED_DATASETS, SAMPLE, SAMPLE_DATASETS,
                      SAMPLE_TICKERS, access_tier, explain, is_key_free, provenance)

__all__ = ["SAMPLE_TICKERS", "OPEN_DATASETS", "SAMPLE_DATASETS",
           "KEY_REQUIRED_DATASETS", "PRESUMED_KEY_REQUIRED_DATASETS",
           "OPEN", "SAMPLE", "KEY_REQUIRED",
           "access_tier", "provenance", "is_key_free", "explain"]
