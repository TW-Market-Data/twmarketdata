"""The TWMD client.

One generic request path serves all 82 datasets. Everything that differs between
them -- route, entity parameter spelling, date parameter spelling, offset
support, gap support, point-in-time semantics -- is looked up in the registry
rather than learned by the caller.
"""
from __future__ import annotations

import os
import warnings
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from . import gaps as _gaps
from . import registry
from ._http import Response, Transport
from ._legacy import LegacyClientMixin
from ._methods import DatasetMethods
from .envelope import extract_count, extract_gaps, extract_provenance, extract_rows
from .errors import FreeTierSymbolError, TwmdConfigError, UnsupportedParameterError
from .frame import to_frame
from .meta import (DatasetStatusWarning, Gap, ImputedKnowledgeDateWarning, Meta,
                   TruncatedResultWarning)
from .pit import (apply_as_of, refuse_or_filter, resolve_mode, scan_knowledge_dates,
                  unsafe_refusal)
from .registry import DatasetInfo

__all__ = ["Client", "TWMarketDataClient"]

MAX_LIMIT = 5000
MAX_PAGES = 100
_ENV_KEY = "TWMD_API_KEY"


def _page_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    """Cheap identity for a page, used to detect a server ignoring `offset`."""
    import hashlib
    import json as _json
    head = rows[:3]
    blob = _json.dumps(head, sort_keys=True, default=str)
    return "%d:%s" % (len(rows), hashlib.sha1(blob.encode("utf-8")).hexdigest())


class Client(DatasetMethods, LegacyClientMixin):
    """Entry point.

    >>> from twmd import Client
    >>> c = Client()                       # no key: free-tier demo symbols
    >>> df = c.daily_price("2330")         # doctest: +SKIP

    With a key, every dataset the plan includes is available::

        c = Client("your_api_key")         # or set TWMD_API_KEY

    The key is read from the ``api_key`` argument first, then ``TWMD_API_KEY``.
    It is never logged and never appears in ``repr()``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 5,
        max_concurrency: int = 2,
        default_limit: int = MAX_LIMIT,
        session: Any = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get(_ENV_KEY)
        if key is not None:
            key = key.strip()
            if not key:
                raise TwmdConfigError(
                    "api_key was provided but empty. Pass a real key, or omit it "
                    "entirely to use the free-tier demo symbols."
                )
        self._api_key = key
        self.default_limit = min(int(default_limit), MAX_LIMIT)
        self._transport = Transport(
            base_url=base_url or registry.DEFAULT_BASE_URL,
            api_key=key,
            timeout=timeout,
            max_retries=max_retries,
            max_concurrency=max_concurrency,
            session=session,
        )
        self.last_meta: Optional[Meta] = None
        """Metadata from the most recent call.

        Also on the returned frame as ``df.twmd``, but kept here too because a
        few pandas operations drop frame metadata.
        """
        self.last_response: Optional[Response] = None
        self._calendar_cache: Optional[List[str]] = None

    # ------------------------------------------------------------------ misc
    @property
    def has_api_key(self) -> bool:
        return self._api_key is not None

    def __repr__(self) -> str:
        state = "api_key=***" if self._api_key else "api_key=None (free tier)"
        return "Client(%s, base_url=%r)" % (state, self._transport.base_url)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    # --------------------------------------------------------------- generic
    def dataset(
        self,
        dataset: str,
        *,
        ticker: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        as_of: Optional[str] = None,
        as_of_policy: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        paginate: bool = True,
        derive_gaps: bool = False,
        raw: bool = False,
        **extra: Any,
    ) -> Any:
        """Query any of the 82 sellable datasets.

        Args:
            dataset: dataset key, e.g. ``"monthly_revenue"``. ``twmd.datasets()``
                lists them; kebab route slugs are accepted too.
            ticker: security identifier. Translated to whichever of ``ticker`` /
                ``symbol`` / ``cb_id`` / ``contract`` / ... this route expects.
            start, end: date bounds, translated to this route's spelling.
            as_of: point-in-time cutoff. Raises
                :class:`~twmd.errors.PointInTimeUnavailable` on datasets that
                cannot honour it rather than returning a frame that merely looks
                replayed. See :mod:`twmd.pit`.
            as_of_policy: pass ``"declared_field"`` to force ``as_of`` on a
                dataset flagged ``point_in_time_safe=false``, accepting the
                look-ahead risk.
            limit: rows per request, capped at 5000 by the API.
            offset: starting row, on the 9 routes that support it.
            paginate: follow ``offset`` to completion where supported.
            derive_gaps: on daily per-entity datasets whose route has no
                ``include_data_gaps``, spend one extra request on
                ``trading_calendar`` and report missing sessions.
            raw: return the decoded JSON envelope instead of a DataFrame.
            **extra: route-specific parameters (see
                ``twmd.capabilities(dataset)["filters"]``).

        Returns:
            A ``TwmdFrame`` (a ``pandas.DataFrame`` carrying ``.twmd`` metadata),
            or ``list[dict]`` when pandas is absent, or the raw envelope when
            ``raw=True``.
        """
        info = registry.get(dataset)
        mode = resolve_mode(info, as_of_policy) if as_of else None

        params = self._build_params(info, ticker=ticker, start=start, end=end,
                                    as_of=as_of, mode=mode, extra=extra)
        # Each route sets its own row cap; sending more is a 422 on some routes
        # and a silent clamp on others, so clamp here and say so.
        route_max = info.limit_max or MAX_LIMIT
        requested = int(limit if limit is not None else self.default_limit)
        use_limit = min(requested, route_max, MAX_LIMIT)
        params["limit"] = use_limit
        limit_clamped = limit is not None and requested > use_limit
        if offset is not None:
            if not info.supports_offset:
                raise UnsupportedParameterError(info.key, "offset", info.supported_filters())
            params["offset"] = offset
        if info.supports_data_gaps:
            params["include_data_gaps"] = "true"

        rows, response, pages, offset_ignored = self._fetch(
            info, params, use_limit, paginate, offset)
        if raw:
            self.last_response = response
            return response.payload

        meta = self._build_meta(info, response, rows, use_limit, pages,
                                offset_ignored=offset_ignored)
        if limit_clamped:
            note = ("limit=%d was reduced to %d, the maximum this route accepts."
                    % (requested, use_limit))
            warnings.warn(note, TruncatedResultWarning, stacklevel=4)
            meta.warnings.append(note)

        if as_of and mode == "client_unsafe_probe":
            # The registry called this dataset unsafe, but a server-supplied
            # knowledge_date outranks that. Decide on the rows, not the snapshot.
            if not refuse_or_filter(info, rows):
                raise unsafe_refusal(info)
            mode = "client_unsafe"

        if as_of and mode and mode != "server":
            rows = apply_as_of(rows, info=info, as_of=as_of, mode=mode,
                               meta=meta, truncated=meta.truncated)
            meta.row_count = len(rows)
        elif as_of:
            meta.as_of_applied = True
            meta.as_of_field = info.as_of_param
            kd = scan_knowledge_dates(rows)
            meta.knowledge_date_present = kd["present"]
            meta.knowledge_date_imputed_rows = kd["imputed"]
            meta.knowledge_date_sources = list(kd["sources"])
            # Server-side filtering is still filtering on imputed dates when the
            # rows say so. Measured 2026-08-12: income_statement, balance_sheet,
            # cash_flow_statement and financial_ratios return kd_imputed=true on
            # every row. Warning only in client mode would leave exactly the
            # people doing server-side PIT backtests uninformed.
            if kd["imputed"]:
                note = (
                    "%d of %d rows carry kd_imputed=true%s: the server filtered on a "
                    "knowledge date derived from a statutory filing deadline, not one "
                    "observed from an announcement. Treat this as a rule-based "
                    "approximation of what was knowable."
                    % (kd["imputed"], len(rows),
                       " (kd_source=%s)" % ", ".join(kd["sources"]) if kd["sources"] else "")
                )
                warnings.warn(note, ImputedKnowledgeDateWarning, stacklevel=3)
                meta.warnings.append(note)

        self._attach_gaps(info, rows, meta, response, derive_gaps)
        self._warn_on_status(info, meta)

        self.last_meta = meta
        self.last_response = response
        return to_frame(rows, meta, columns=info.columns or None)

    # ----------------------------------------------------------- ergonomics
    def daily_price(
        self,
        ticker: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: Optional[int] = None,
        raw: bool = False,
    ) -> Any:
        """Daily OHLCV across both boards, with a ``market`` column.

        TWSE and TPEx are separate datasets. This queries both and concatenates.
        Rows are never silently de-duplicated: if a ticker appears on both boards
        for the same date, both rows are returned and a warning is recorded, so
        an overlap surfaces instead of being resolved by guesswork.
        """
        frames: List[Dict[str, Any]] = []
        metas: List[Meta] = []
        for key, market in (("twse_daily_price", "TWSE"), ("tpex_daily_price", "TPEx")):
            rows = self.dataset(key, ticker=ticker, start=start, end=end,
                                limit=limit, raw=True)
            extracted, _ = extract_rows(rows)
            for row in extracted:
                enriched = dict(row)
                enriched.setdefault("market", market)
                frames.append(enriched)
            if self.last_meta:
                metas.append(self.last_meta)

        meta = Meta(dataset="daily_price", route="twse_daily_price+tpex_daily_price")
        meta.row_count = len(frames)
        meta.tier_required = "free"
        meta.registry_status = "active"
        meta.truncated = any(m.truncated for m in metas)
        meta.warnings = [w for m in metas for w in m.warnings]

        seen: Dict[Any, int] = {}
        for row in frames:
            k = (row.get("symbol") or row.get("ticker"), row.get("date") or row.get("trade_date"))
            seen[k] = seen.get(k, 0) + 1
        overlaps = sum(1 for v in seen.values() if v > 1)
        if overlaps:
            meta.warnings.append(
                "%d (ticker, date) pairs appear on both boards. Both rows are kept; "
                "use the market column to choose." % overlaps
            )

        self.last_meta = meta
        if raw:
            return frames
        return to_frame(frames, meta)

    # -------------------------------------------------------------- helpers
    def _build_params(
        self,
        info: DatasetInfo,
        *,
        ticker: Optional[str],
        start: Optional[str],
        end: Optional[str],
        as_of: Optional[str],
        mode: Optional[str],
        extra: Mapping[str, Any],
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        extra = dict(extra)

        # 13 routes are keyed by something that is not a stock ticker -- cb_id,
        # contract, index_code, issuer. Accept the route's own name as a keyword
        # so `issuer="..."` reads correctly, rather than forcing everything
        # through `ticker=` and silently sending a stock code as an issuer code.
        native = info.entity_param
        if native and native in extra:
            if ticker is not None:
                raise UnsupportedParameterError(
                    info.key, "%s (already given as ticker=)" % native,
                    info.supported_filters())
            ticker = extra.pop(native)

        if ticker is not None:
            if not info.entity_param:
                raise UnsupportedParameterError(info.key, "ticker", info.supported_filters())
            if info.entity_is_stock_ticker:
                self._check_free_tier_symbol(ticker)
            params[info.entity_param] = ticker

        if start is not None:
            if not info.start_param:
                raise UnsupportedParameterError(info.key, "start", info.supported_filters())
            params[info.start_param] = start

        if end is not None:
            if not info.end_param:
                raise UnsupportedParameterError(info.key, "end", info.supported_filters())
            params[info.end_param] = end

        # Only server mode puts as_of on the wire; the client modes filter after.
        if as_of is not None and mode == "server" and info.as_of_param:
            params[info.as_of_param] = as_of

        allowed = set(info.other_params)
        for name, value in extra.items():
            if name not in allowed:
                raise UnsupportedParameterError(info.key, name, info.supported_filters())
            params[name] = value

        return params

    def _check_free_tier_symbol(self, ticker: str) -> None:
        if self._api_key:
            return
        allowed = registry.free_tier_symbols()
        if str(ticker) not in allowed:
            raise FreeTierSymbolError(str(ticker), allowed)

    def _fetch(
        self,
        info: DatasetInfo,
        params: Dict[str, Any],
        use_limit: int,
        paginate: bool,
        offset: Optional[int],
    ) -> Any:
        response = self._transport.get(info.route, params, dataset=info.key)
        rows, _row_key = extract_rows(response.payload)
        pages = 1
        offset_ignored = False

        if paginate and info.supports_offset and len(rows) >= use_limit:
            seen = {_page_fingerprint(rows)}
            cursor = (offset or 0) + len(rows)
            while pages < MAX_PAGES:
                page_params = dict(params, offset=cursor)
                page = self._transport.get(info.route, page_params, dataset=info.key)
                page_rows, _ = extract_rows(page.payload)
                pages += 1
                if not page_rows:
                    break

                # Some routes accept `offset` and ignore it -- measured on
                # index-constituents 2026-08-12, where offset=0/3/6 all returned
                # the identical page. Without this check the loop would append
                # the same rows forever and call the duplicates a full history.
                fingerprint = _page_fingerprint(page_rows)
                if fingerprint in seen:
                    offset_ignored = True
                    break
                seen.add(fingerprint)

                rows.extend(page_rows)
                cursor += len(page_rows)
                if len(page_rows) < use_limit:
                    break
        return rows, response, pages, offset_ignored

    def _build_meta(self, info: DatasetInfo, response: Response,
                    rows: Sequence[Mapping[str, Any]], use_limit: int,
                    pages: int, *, offset_ignored: bool = False) -> Meta:
        _, row_key = extract_rows(response.payload)
        provenance = extract_provenance(response.payload)

        # Truncated when the limit was hit and we could not page past it --
            # either the route has no offset, or it has one and ignores it.
        truncated = len(rows) >= use_limit and (not info.supports_offset or offset_ignored)
        meta = Meta(
            dataset=info.key,
            route=info.route,
            row_count=len(rows),
            truncated=truncated,
            limit_used=use_limit,
            supports_offset=info.supports_offset,
            tier_required=info.tier,
            registry_status=info.status,
            knowledge_time_field=info.knowledge_time_field,
            point_in_time_safe=info.point_in_time_safe,
            pit_caveat=info.as_of_note,
            as_of_mode=info.as_of_mode,
            coverage_min=info.coverage_min,
            coverage_max=info.coverage_max,
            data_as_of=provenance["data_as_of"],
            source_role=provenance["source_role"],
            lineage=provenance["lineage"],
            request_id=response.request_id,
            status_code=response.status_code,
            warnings=list(provenance["warnings"]),
            raw_envelope_keys=sorted(response.payload)
            if isinstance(response.payload, Mapping) else [],
            row_key=row_key,
        )
        meta.row_count = extract_count(response.payload, len(rows)) if pages == 1 else len(rows)
        meta.row_count = len(rows)

        meta.offset_ignored = offset_ignored
        if offset_ignored:
            note = (
                "This route accepts `offset` but returned an identical page for a "
                "different offset, so it does not actually paginate. Pagination stopped "
                "after %d page(s) rather than appending duplicate rows; the result is "
                "incomplete. Narrow start/end to fetch the rest." % pages
            )
            warnings.warn(note, TruncatedResultWarning, stacklevel=4)
            meta.warnings.append(note)
        elif truncated:
            note = (
                "Hit the row limit of %d and this route has no offset parameter, so the "
                "result is incomplete. Narrow start/end to fetch the rest." % use_limit
            )
            warnings.warn(note, TruncatedResultWarning, stacklevel=4)
            meta.warnings.append(note)
        return meta

    def _attach_gaps(self, info: DatasetInfo, rows: Sequence[Mapping[str, Any]],
                     meta: Meta, response: Response, derive: bool) -> None:
        server_gaps = extract_gaps(response.payload)
        if server_gaps is not None:
            meta.data_gaps = server_gaps
            meta.gaps_source = "server"
            return

        if not derive:
            meta.gaps_source = "unsupported" if not info.supports_data_gaps else "unknown"
            return

        column = _gaps.pick_date_column(rows)
        if not column or not rows:
            meta.gaps_source = "unsupported"
            return

        calendar = self._trading_days()
        if not calendar:
            meta.gaps_source = "unknown"
            return

        meta.data_gaps = _gaps.derive_gaps(rows, calendar, date_column=column)
        meta.gaps_source = "client_derived"

    def _trading_days(self) -> List[str]:
        if self._calendar_cache is not None:
            return self._calendar_cache
        try:
            payload = self.dataset("trading_calendar", raw=True, limit=MAX_LIMIT)
        except Exception:
            self._calendar_cache = []
            return self._calendar_cache
        rows, _ = extract_rows(payload)
        days = []
        for row in rows:
            if row.get("is_trading") in (False, "false", 0):
                continue
            value = row.get("trade_date") or row.get("date")
            if value:
                days.append(str(value)[:10])
        self._calendar_cache = sorted(set(days))
        return self._calendar_cache

    @staticmethod
    def _warn_on_status(info: DatasetInfo, meta: Meta) -> None:
        if info.status != "active":
            note = (
                "Dataset %r has registry_status=%r. Treat the series as incomplete: "
                "this is not a full production dataset yet." % (info.key, info.status)
            )
            warnings.warn(note, DatasetStatusWarning, stacklevel=4)
            meta.warnings.append(note)


class TWMarketDataClient(Client):
    """Deprecated alias for :class:`Client`, kept so 0.1.0 imports still resolve.

    0.1.0 required an API key and defaulted to ``https://twmarketdata.com``,
    which now returns ``410 endpoint_retired``. This subclass keeps the old name
    but uses the current base URL and allows key-less free-tier use.
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs: Any) -> None:
        warnings.warn(
            "TWMarketDataClient is deprecated; use twmd.Client. The 0.1.0 default "
            "base_url (https://twmarketdata.com) is retired and now returns HTTP 410 "
            "-- this alias uses https://api.twmarketdata.com/v2 instead.",
            DeprecationWarning, stacklevel=2,
        )
        super().__init__(api_key, **kwargs)

    def get_dataset(self, dataset: str, **params: Any) -> Any:
        """0.1.0-shaped generic call. Accepts kebab route slugs."""
        return self.dataset(dataset, **params)
