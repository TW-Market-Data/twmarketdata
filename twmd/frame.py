"""DataFrame return type.

``TwmdFrame`` is a real ``pandas.DataFrame`` subclass, so it passes
``isinstance`` checks and works anywhere a DataFrame works -- the two-line
quickstart has to stay true. Metadata rides along in ``df.twmd``.

Honest limitation, documented rather than papered over: pandas preserves
``_metadata`` through slicing and copying, but some operations (notably
``merge`` and several groupby paths) construct a fresh frame and drop it. So the
same :class:`~twmd.meta.Meta` is always available on the client as
``client.last_meta``, which no pandas operation can lose.

Without pandas installed the SDK still works and returns ``list[dict]``; the
metadata is then only on the client.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from .meta import Meta

if TYPE_CHECKING:  # pragma: no cover
    import pandas

__all__ = ["TwmdFrame", "pandas_available", "to_frame"]

try:  # pragma: no cover - exercised by whichever env runs the tests
    import pandas as _pd

    _PANDAS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _pd = None  # type: ignore[assignment]
    _PANDAS_AVAILABLE = False


def pandas_available() -> bool:
    return _PANDAS_AVAILABLE


if _PANDAS_AVAILABLE:

    class TwmdFrame(_pd.DataFrame):  # type: ignore[misc,name-defined]
        """A DataFrame that carries its :class:`~twmd.meta.Meta` as ``.twmd``."""

        _metadata = ["twmd"]

        @property
        def _constructor(self) -> Any:
            return TwmdFrame

        @property
        def meta(self) -> Optional[Meta]:
            """Alias for ``.twmd``; None if a pandas op dropped the metadata."""
            return getattr(self, "twmd", None)

else:  # pragma: no cover

    class TwmdFrame:  # type: ignore[no-redef]
        """Placeholder raised on use when pandas is not installed."""

        def __init__(self, *_a: Any, **_kw: Any) -> None:
            raise ImportError(
                "pandas is required for DataFrame output. Install it with "
                "`pip install twmarketdata[pandas]`, or call with raw=True to get "
                "plain dicts."
            )


def to_frame(rows: Sequence[Dict[str, Any]], meta: Meta,
             columns: Optional[List[str]] = None) -> Any:
    """Build a ``TwmdFrame`` from rows, or return the rows unchanged sans pandas."""
    if not _PANDAS_AVAILABLE:
        return list(rows)

    frame = TwmdFrame(list(rows))
    if frame.empty and columns:
        # An empty result still gets the dataset's real column names, so
        # downstream code that selects columns fails the same way it would
        # with data rather than with a confusing KeyError on an empty frame.
        frame = TwmdFrame({c: [] for c in columns})
    frame.twmd = meta
    return frame
