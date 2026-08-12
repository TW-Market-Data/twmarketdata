"""Compatibility layers.

``twmd.compat.finmind`` mirrors the public call signatures of the open-source
FinMind package so existing code can run against TW Market Data. It is interop,
not impersonation: see NOTICE for the trademark position, and
``mapping/finmind_map.csv`` for what every call maps to (or does not).
"""
from __future__ import annotations

__all__ = ["finmind"]

from . import finmind  # noqa: F401
