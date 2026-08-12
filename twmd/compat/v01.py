"""Re-export of the 0.1.0 surface for ``from twmd.compat import v01``.

The implementation lives in :mod:`twmd._legacy` so that :mod:`twmd.client` can
mix the legacy methods into the main client without an import cycle.
"""
from __future__ import annotations

from .._legacy import *  # noqa: F401,F403
from .._legacy import __all__  # noqa: F401
