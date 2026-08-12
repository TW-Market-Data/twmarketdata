"""FinMind-shaped calls, served by TW Market Data.

    from twmd.compat import finmind as fm
    df = fm.taiwan_stock_daily(stock_id="2330", start_date="2020-01-01")

The point is that existing call sites keep working. What this module will not do
is pretend a mapping exists when it does not: calls with no TWMD equivalent
raise :class:`~twmd.errors.NotMappedError` rather than returning an empty frame,
because an empty frame is indistinguishable from "your query matched nothing".

Every mapping is graded, and the grade decides the behaviour:

===== ============================================ ==========================
Grade Meaning                                      Behaviour
===== ============================================ ==========================
A     same grain and meaning, field renames only   returns data
B     same fact, different shape                   reshapes, or refuses if the
                                                   reshape is not implemented
C     no same-named equivalent; TWMD covers it     returns data + warns about
      differently                                  the difference
D     no equivalent in the 82 sellable datasets    raises NotMappedError
===== ============================================ ==========================

Mappings graded ``low`` confidence also raise, until they have been checked row
by row against live data.

**Column names are TWMD's.** Parameter names are mirrored because they are
visible in the public signatures; response column names are not, and this SDK
will not invent them from memory. Where an identifier column exists, a
``stock_id`` alias is added for convenience. ``mapping/finmind_map.csv`` records
what each call maps to.

This project is not affiliated with, endorsed by, or sponsored by FinMind; see
NOTICE.
"""
from __future__ import annotations

import json
import os
import warnings
from typing import Any, Dict, List, Optional

from ..client import Client
from ..errors import NotMappedError
from ..meta import CompatSubstitutionWarning

__all__ = ["set_client", "get_client", "login_by_token", "mapping_for",
           "supported_calls", "unsupported_calls", "FINMIND_SOURCE"]

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_finmind_map.json")
with open(_PATH, encoding="utf-8") as _fh:
    _MAP: Dict[str, Any] = json.load(_fh)

FINMIND_SOURCE: str = _MAP["finmind_source"]
_METHODS: Dict[str, Dict[str, Any]] = _MAP["methods"]

_client: Optional[Client] = None

# Reshapes that are implemented and covered by tests. A grade-B mapping without
# an entry here refuses rather than returning the wrong shape.
_RESHAPERS: Dict[str, str] = {}


def set_client(client: Client) -> None:
    """Use a specific client (e.g. one carrying an API key)."""
    global _client
    _client = client


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client()
    return _client


def login_by_token(api_token: Optional[str] = None, **_kw: Any) -> Client:
    """Accepts a token and configures the TWMD client with it.

    Named to match the FinMind entry point so existing setup code runs. The
    token is a TWMD API key -- FinMind credentials are not accepted or used.
    """
    set_client(Client(api_token))
    return get_client()


def mapping_for(call: str) -> Optional[Dict[str, Any]]:
    """The mapping record for a FinMind call name, or None if unrecognised."""
    entry = _METHODS.get(call)
    return dict(entry) if entry else None


def supported_calls() -> List[str]:
    """FinMind calls this module will actually serve."""
    return sorted(k for k, v in _METHODS.items() if _servable(v))


def unsupported_calls() -> Dict[str, str]:
    """FinMind calls that raise, mapped to why."""
    return {k: _refusal_reason(k, v) for k, v in sorted(_METHODS.items())
            if not _servable(v)}


# --------------------------------------------------------------------- engine
def _servable(entry: Dict[str, Any]) -> bool:
    if entry["tier"] == "D" or entry["confidence"] == "low":
        return False
    if entry["tier"] == "B" and not entry["twmd"]:
        return False
    return bool(entry["twmd"])


def _refusal_reason(call: str, entry: Dict[str, Any]) -> str:
    if entry["tier"] == "D":
        return entry["note"] or "no equivalent among the 82 sellable TWMD datasets"
    if entry["confidence"] == "low":
        return (
            "a candidate mapping to %s exists but has not been verified row by row, "
            "so it is withheld rather than shipped possibly-wrong. %s"
            % (", ".join(entry["twmd"]) or "(none)", entry["note"])
        ).strip()
    return entry["note"] or "not mapped"


def _call(name: str, *, stock_id: Any = None, start_date: Optional[str] = None,
          end_date: Optional[str] = None, as_of: Optional[str] = None,
          **kwargs: Any) -> Any:
    entry = _METHODS.get(name)
    if entry is None:
        raise NotMappedError(name, "not a recognised FinMind call in %s" % FINMIND_SOURCE)

    if not _servable(entry):
        raise NotMappedError(
            name, _refusal_reason(name, entry),
            suggestion=", ".join(entry["twmd"]) or None,
        )

    if entry["tier"] == "B" and name not in _RESHAPERS:
        raise NotMappedError(
            name,
            "TWMD has this data in %s but with a different row shape, and the reshape "
            "for this call is not implemented yet. Call twmd.Client().%s(...) to get "
            "the TWMD shape directly."
            % (", ".join(entry["twmd"]), entry["twmd"][0]),
            suggestion=", ".join(entry["twmd"]),
        )

    if entry["tier"] == "C":
        warnings.warn(
            "%s is served by TWMD dataset %s, which is not a like-for-like "
            "replacement: %s" % (name, ", ".join(entry["twmd"]), entry["note"]),
            CompatSubstitutionWarning, stacklevel=3,
        )
    elif entry["confidence"] == "medium":
        warnings.warn(
            "%s maps to %s, but field-level equivalence has not been verified against "
            "live rows yet. Check the columns before relying on them."
            % (name, ", ".join(entry["twmd"])),
            CompatSubstitutionWarning, stacklevel=3,
        )

    client = get_client()
    ticker = _first(stock_id) if stock_id is not None else None

    if len(entry["twmd"]) > 1 and set(entry["twmd"]) == {"twse_daily_price", "tpex_daily_price"}:
        return client.daily_price(ticker, start=start_date, end=end_date, **kwargs)

    dataset = entry["twmd"][0]
    result = client.dataset(dataset, ticker=ticker, start=start_date, end=end_date,
                            as_of=as_of, **kwargs)
    return _add_stock_id_alias(result)


def _first(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _add_stock_id_alias(result: Any) -> Any:
    """Expose the identifier column as ``stock_id`` as well, where one exists."""
    try:
        columns = list(result.columns)
    except AttributeError:
        return result
    if "stock_id" in columns:
        return result
    for candidate in ("symbol", "ticker"):
        if candidate in columns:
            result["stock_id"] = result[candidate]
            break
    return result


def _make(name: str) -> Any:
    def method(stock_id: Any = None, start_date: Optional[str] = None,
               end_date: Optional[str] = None, **kwargs: Any) -> Any:
        return _call(name, stock_id=stock_id, start_date=start_date,
                     end_date=end_date, **kwargs)

    entry = _METHODS[name]
    method.__name__ = name
    if _servable(entry):
        doc = "Grade %s mapping to TWMD %s (confidence: %s).\n\n%s" % (
            entry["tier"], ", ".join(entry["twmd"]), entry["confidence"], entry["note"])
    else:
        doc = "Raises NotMappedError: %s" % _refusal_reason(name, entry)
    method.__doc__ = doc + "\n\nMapping source: %s" % FINMIND_SOURCE
    return method


for _name in _METHODS:
    globals()[_name] = _make(_name)
    __all__.append(_name)

del _name
