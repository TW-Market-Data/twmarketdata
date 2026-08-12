"""Generated dataset methods -- do not edit by hand.

Regenerate with::

    python tools/build_mapping.py && python tools/gen_registry.py && python tools/gen_methods.py

Every method here is a thin call through to :meth:`twmd.Client.dataset`, which
does the parameter translation, pagination, point-in-time handling and gap
reporting. The value of the named methods is discoverability and typing.
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = ["DatasetMethods"]


class DatasetMethods:
    """Mixin providing one method per sellable dataset (82 of them)."""

    def attention_disposal_events(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """注意/處置事件 -- tier=pro, status=active.

        Route: /v2/datasets/attention-disposal-events
        as_of: client_unsafe. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'event_date' declared but
        point_in_time_safe=false; local filtering on it may look ahead, so as_of
        is refused unless the caller opts in explicitly

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('attention_disposal_events', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def balance_sheet(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """財報-資產負債表 -- tier=pro, status=active.

        Grain: one row per (ticker, fiscal_year, fiscal_quarter).
        Route: /v2/datasets/balance-sheet
        as_of: server. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_period'
            end: sent as 'end_period'
        """
        return self.dataset('balance_sheet', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def block_trade_daily(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Block Trade Daily -- tier=developer, status=active.

        Route: /v2/datasets/block-trade-daily
        as_of: client. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('block_trade_daily', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def bond_convertible_reference(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """可轉債參考主檔 -- tier=free, status=active.

        Route: /v2/datasets/bond-convertible-reference
        as_of: client. data_gaps: server. pagination: limit only.
        Runs without an API key on the demo symbols.

        Args:
            ticker: security id (sent as 'issuer')
        """
        return self.dataset('bond_convertible_reference', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def bond_yield_curve(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """台灣公債殖利率曲線 -- tier=max, status=active.

        Grain: one row per (tenor, trade_date).
        Route: /v2/datasets/bond-yield-curve
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('bond_yield_curve', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def broker_branch_reference(self, *, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """券商分點名冊 -- tier=free, status=active.

        Route: /v2/datasets/broker-branch-reference
        as_of: client. data_gaps: server. pagination: limit only.
        Runs without an API key on the demo symbols.
        """
        return self.dataset('broker_branch_reference', as_of=as_of, limit=limit, raw=raw, **extra)

    def capital_formation_events(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """資本形成事件(增/減資) -- tier=starter, status=active.

        Grain: one row per (ticker, market, event_date, event_type).
        Route: /v2/datasets/capital-formation-events
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('capital_formation_events', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def cash_flow_statement(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """財報-現金流量表 -- tier=pro, status=active.

        Grain: one row per (ticker, fiscal_year, fiscal_quarter).
        Route: /v2/datasets/cash-flow-statement
        as_of: server. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_period'
            end: sent as 'end_period'
        """
        return self.dataset('cash_flow_statement', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def company_industry_exposures(self, *, ticker: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """公司產業曝險 -- tier=free, status=active.

        Route: /v2/datasets/company-industry-exposures
        as_of: unsupported. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.

        PIT note: no knowledge axis; as_of refused by design

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('company_industry_exposures', ticker=ticker, limit=limit, raw=raw, **extra)

    def company_news(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Company News -- tier=pro, status=active.

        Route: /v2/datasets/company-news
        as_of: client_unsafe. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'published_at' declared but
        point_in_time_safe=false; local filtering on it may look ahead, so as_of
        is refused unless the caller opts in explicitly

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('company_news', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def company_peer_groups(self, *, ticker: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """同業對照組 -- tier=free, status=active.

        Route: /v2/datasets/company-peer-groups
        as_of: unsupported. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.

        PIT note: no knowledge axis; as_of refused by design

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('company_peer_groups', ticker=ticker, limit=limit, raw=raw, **extra)

    def competitor_fx(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """競貨幣匯率(JPY/KRW/CNY vs TWD) -- tier=starter, status=active.

        Grain: one row per (rate_date).
        Route: /v2/datasets/competitor-fx
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('competitor_fx', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def convertible_bond_institutional(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """可轉債法人買賣 -- tier=max, status=active.

        Grain: one row per (cb_id, trade_date).
        Route: /v2/datasets/convertible-bond-institutional
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'cb_id')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('convertible_bond_institutional', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def convertible_bond_monthly(self, *, ticker: Optional[str] = None, start: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """可轉債集保月報 -- tier=max, status=active.

        Grain: one row per (cb_id, data_month).
        Route: /v2/datasets/convertible-bond-monthly
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'cb_id')
            start: sent as 'data_month'
        """
        return self.dataset('convertible_bond_monthly', ticker=ticker, start=start, as_of=as_of, limit=limit, raw=raw, **extra)

    def convertible_bond_overview(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """可轉債總覽 -- tier=max, status=active.

        Grain: one row per (cb_id, trade_date).
        Route: /v2/datasets/convertible-bond-overview
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'cb_id')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('convertible_bond_overview', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def corporate_actions(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """除權除息參考價 / Ex-Right & Ex-Dividend Reference Prices -- tier=pro, status=partial.

        Route: /v2/datasets/corporate-actions
        as_of: client_unsafe. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'event_date' declared but
        point_in_time_safe=false; local filtering on it may look ahead, so as_of
        is refused unless the caller opts in explicitly

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('corporate_actions', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def customs_trade_monthly(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """海關進出口貿易統計 -- tier=starter, status=active.

        Grain: one row per (stat_item, item_code, period_month).
        Route: /v2/datasets/customs-trade-monthly
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('customs_trade_monthly', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def day_trading_suspension(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """當沖警示/暫停 -- tier=pro, status=active.

        Route: /v2/datasets/day-trading-suspension
        as_of: unsupported. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: no knowledge axis; as_of refused by design

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('day_trading_suspension', ticker=ticker, start=start, end=end, limit=limit, raw=raw, **extra)

    def derivatives_market(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Derivatives Market (TAIFEX 期貨日) -- tier=max, status=active.

        Route: /v2/datasets/derivatives-market
        as_of: server. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('derivatives_market', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def dividends(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """股利與配息時程 / Dividends & Distribution Schedule -- tier=pro, status=partial.

        Route: /v2/datasets/dividends
        as_of: client_unsafe. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'announcement_date' declared but
        point_in_time_safe=false; local filtering on it may look ahead, so as_of
        is refused unless the caller opts in explicitly

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('dividends', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def esg_ghg_carbon_disclosure(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """GHG Carbon Disclosure (溫室氣體碳揭露) -- tier=developer, status=active.

        Route: /v2/datasets/esg-ghg-carbon-disclosure
        as_of: server. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('esg_ghg_carbon_disclosure', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def etf_holdings(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """ETF Holdings (ETF 成分持股) -- tier=developer, status=active.

        Route: /v2/datasets/etf-holdings
        as_of: server. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'issuer')
        """
        return self.dataset('etf_holdings', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def export_orders_monthly(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """外銷訂單金額(按貨品別) -- tier=starter, status=active.

        Grain: one row per (stat_item, item_code, period_month).
        Route: /v2/datasets/export-orders-monthly
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('export_orders_monthly', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def financial_ratios(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """財務比率 -- tier=pro, status=active.

        Grain: one row per (ticker, fiscal_year, fiscal_quarter).
        Route: /v2/datasets/financial-metrics
        as_of: server. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('financial_ratios', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def foreign_holding(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """外資持股比率 -- tier=pro, status=active.

        Grain: one row per (ticker, trade_date).
        Route: /v2/datasets/foreign-holding
        as_of: client. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('foreign_holding', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def fund_etf_metadata(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Fund / ETF Metadata (基金·ETF 基本資料) -- tier=free, status=active.

        Route: /v2/datasets/fund-etf-metadata
        as_of: server. data_gaps: server. pagination: limit only.
        Runs without an API key on the demo symbols.

        Args:
            ticker: security id (sent as 'issuer')
        """
        return self.dataset('fund_etf_metadata', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def futures_daily_context(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """期貨日情境(基差/近月/法人OI) -- tier=starter, status=active.

        Grain: one row per (contract, trade_date).
        Route: /v2/datasets/futures-daily-context
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'contract')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('futures_daily_context', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def governance_t187ap33_l(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Governance Chairman/GM Duality (t187ap33_L) -- tier=developer, status=active.

        Route: /v2/datasets/governance-t187ap33-l
        as_of: server. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('governance_t187ap33_l', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def income_statement(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """財報-損益表 -- tier=pro, status=active.

        Grain: one row per (ticker, fiscal_year, fiscal_quarter).
        Route: /v2/datasets/income-statement
        as_of: server. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('income_statement', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def index_constituents(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Index Constituents (指數成分股) -- tier=free, status=active.

        Route: /v2/datasets/index-constituents
        as_of: server. data_gaps: not on this route. pagination: offset.
        Runs without an API key on the demo symbols.

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('index_constituents', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def industry_chain(self, *, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """產業價值鏈成員 -- tier=starter, status=active.

        Grain: one row per (ticker, chain_name, node_name, capture_date).
        Route: /v2/datasets/industry-chain
        as_of: client_unsafe. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'capture_date' declared but
        point_in_time_safe=false; local filtering on it may look ahead, so as_of
        is refused unless the caller opts in explicitly
        """
        return self.dataset('industry_chain', as_of=as_of, limit=limit, raw=raw, **extra)

    def industry_index(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """產業別指數日線 -- tier=free, status=planned.

        Grain: one row per (industry_name, trade_date, market).
        Route: /v2/datasets/index-classification
        as_of: client_unverified. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'trade_date' declared but absent from the
        published schema; SDK verifies at runtime

        Args:
            ticker: security id (sent as 'index_code')
        """
        return self.dataset('industry_index', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def industry_index_daily(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Industry Index Daily -- tier=starter, status=partial.

        Route: /v2/datasets/industry-index-daily
        as_of: client. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('industry_index_daily', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def institutional_flow(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """三大法人買賣超(合計) -- tier=starter, status=active.

        Grain: one row per (ticker, trade_date, market).
        Route: /v2/datasets/institutional-flow
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('institutional_flow', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def interest_rate_snapshots(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Interest Rate Snapshots -- tier=developer, status=active.

        Route: /v2/datasets/interest-rate-snapshot
        as_of: server. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('interest_rate_snapshots', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def investor_conference_calendar(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """法人說明會行事曆 -- tier=free, status=active.

        Grain: one row per (ticker, market, conference_date).
        Route: /v2/datasets/investor-conference-calendar
        as_of: client. data_gaps: not on this route. pagination: limit only.

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('investor_conference_calendar', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def issuer_classification(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Issuer Classification -- tier=free, status=active.

        Route: /v2/datasets/issuer-classification
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('issuer_classification', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def issuer_profiles(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Issuer Profiles -- tier=free, status=active.

        Route: /v2/datasets/issuer-profile
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
        """
        return self.dataset('issuer_profiles', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def lending_utilization(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """借券使用率 -- tier=max, status=active.

        Grain: one row per (ticker, market, trade_date).
        Route: /v2/datasets/lending-utilization
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('lending_utilization', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def limit_events(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """漲跌停事件 -- tier=starter, status=active.

        Grain: one row per (symbol, trade_date, direction).
        Route: /v2/datasets/limit-events
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('limit_events', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def macro_global(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Global Macro -- tier=enterprise, status=private_beta.

        Route: /v2/datasets/macro-global
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('macro_global', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def macro_worldbank(self, *, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """World Bank 總體指標 -- tier=developer, status=active.

        Route: /v2/datasets/macro-worldbank
        as_of: client_unsafe. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'year' declared but point_in_time_safe=false;
        local filtering on it may look ahead, so as_of is refused unless the
        caller opts in explicitly
        """
        return self.dataset('macro_worldbank', as_of=as_of, limit=limit, raw=raw, **extra)

    def major_event_taxonomy(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """重大訊息事件分類 -- tier=pro, status=active.

        Grain: one row per (ticker, event_date, event_time, subject).
        Route: /v2/datasets/major-event-taxonomy
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('major_event_taxonomy', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def margin_short(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """融資融券餘額 -- tier=starter, status=active.

        Grain: one row per (ticker, trade_date, market).
        Route: /v2/datasets/margin-short
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('margin_short', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def margin_short_cover_date(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """融券強制回補日 -- tier=pro, status=active.

        Grain: one row per (ticker, cover_date).
        Route: /v2/datasets/margin-short-cover-date
        as_of: unsupported. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: no knowledge axis; as_of refused by design

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('margin_short_cover_date', ticker=ticker, start=start, end=end, limit=limit, raw=raw, **extra)

    def margin_short_total(self, *, start: Optional[str] = None, end: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Margin Short Total -- tier=starter, status=active.

        Route: /v2/datasets/total-margin-short
        as_of: unsupported. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: no knowledge axis declared

        Args:
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('margin_short_total', start=start, end=end, limit=limit, raw=raw, **extra)

    def margin_system_stats(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """信用交易系統統計 -- tier=pro, status=active.

        Grain: one row per (market, trade_date).
        Route: /v2/datasets/margin-system-stats
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('margin_system_stats', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def market_breadth(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Market Breadth -- tier=starter, status=active.

        Route: /v2/datasets/market-breadth
        as_of: server. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('market_breadth', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def market_index(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """大盤/類股指數日線 -- tier=free, status=partial.

        Grain: one row per (index_code, trade_date).
        Route: /v2/datasets/market-index
        as_of: client_unverified. data_gaps: server. pagination: limit only.

        PIT note: knowledge field 'trade_date' declared but absent from the
        published schema; SDK verifies at runtime

        Args:
            ticker: security id (sent as 'index_code')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('market_index', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def market_overview_snapshots(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Market Overview Snapshots -- tier=developer, status=active.

        Route: /v2/datasets/market-overview-snapshots
        as_of: server. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('market_overview_snapshots', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def market_value_weight(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """個股市值權重 -- tier=pro, status=active.

        Grain: one row per (ticker, as_of_date).
        Route: /v2/datasets/market-value-weight
        as_of: server. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('market_value_weight', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def monthly_revenue(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """月營收 -- tier=free, status=active.

        Grain: one row per (ticker, revenue_month).
        Route: /v2/datasets/monthly-revenue
        as_of: client_unsafe. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.

        PIT note: knowledge field 'as_of_date' declared but
        point_in_time_safe=false; local filtering on it may look ahead, so as_of
        is refused unless the caller opts in explicitly

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('monthly_revenue', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def mops_major_event(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """重大訊息(結構化) -- tier=pro, status=partial.

        Grain: one row per (ticker, event_date, event_time, source_group).
        Route: /v2/datasets/mops-major-event
        as_of: client_unverified. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'event_datetime' declared but absent from the
        published schema; SDK verifies at runtime

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('mops_major_event', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def options_daily_taifex(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """TAIFEX Options Daily (選擇權每日行情) -- tier=max, status=active.

        Route: /v2/datasets/options-daily-taifex
        as_of: client. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('options_daily_taifex', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def price_enhanced(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Price Adjustment Factors (價格調整因子) -- tier=starter, status=active.

        Route: /v2/datasets/price-enhanced
        as_of: unsupported. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        PIT note: no knowledge axis declared

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('price_enhanced', ticker=ticker, start=start, end=end, limit=limit, raw=raw, **extra)

    def price_move_context(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """大波動日情境卡 -- tier=starter, status=active.

        Grain: one row per (symbol, trade_date, market).
        Route: /v2/datasets/price-move-context
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('price_move_context', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def production_value_index_monthly(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """製造業生產價值指數 -- tier=starter, status=active.

        Grain: one row per (stat_item, item_code, period_month).
        Route: /v2/datasets/production-value-index-monthly
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('production_value_index_monthly', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def return_index_daily(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """報酬指數(含息) -- tier=pro, status=active.

        Grain: one row per (index_code, trade_date).
        Route: /v2/datasets/return-index-daily
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('return_index_daily', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def securities_firm_master(self, *, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """證券商總表 -- tier=free, status=active.

        Grain: one row per (broker_id).
        Route: /v2/datasets/securities-firm-master
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.
        """
        return self.dataset('securities_firm_master', as_of=as_of, limit=limit, raw=raw, **extra)

    def securities_lending(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """借券/借券賣出 -- tier=starter, status=active.

        Grain: one row per (ticker, trade_date).
        Route: /v2/datasets/securities-lending
        as_of: server. data_gaps: not on this route. pagination: offset.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('securities_lending', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def security_master(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """證券主檔 -- tier=free, status=active.

        Grain: one row per (ticker).
        Route: /v2/datasets/security-master
        as_of: client_unverified. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.

        PIT note: knowledge field 'as_of_date' declared but absent from the
        published schema; SDK verifies at runtime

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('security_master', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def shareholding_concentration(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """集保持股分級集中度 -- tier=starter, status=active.

        Grain: one row per (ticker, market, report_date).
        Route: /v2/datasets/shareholding-concentration
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
        """
        return self.dataset('shareholding_concentration', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

    def short_restriction_flags(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """空方限制旗標 -- tier=max, status=active.

        Grain: one row per (ticker, market, trade_date).
        Route: /v2/datasets/short-restriction-flags
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('short_restriction_flags', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def short_sale_balance_control(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """平盤下融券借券管控 -- tier=max, status=active.

        Grain: one row per (ticker, trade_date).
        Route: /v2/datasets/short-sale-balance-control
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('short_sale_balance_control', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def stock_delisting_lifecycle(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Stock Delisting Lifecycle (下市生命週期) -- tier=free, status=active.

        Route: /v2/datasets/stock-delisting-lifecycle
        as_of: client_unsafe. data_gaps: server. pagination: limit only.
        Runs without an API key on the demo symbols.

        PIT note: knowledge field 'announcement_date' declared but
        point_in_time_safe=false; local filtering on it may look ahead, so as_of
        is refused unless the caller opts in explicitly

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('stock_delisting_lifecycle', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def stock_price_limit_daily(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Stock Price Limit Daily (每日漲跌停價位) -- tier=max, status=active.

        Route: /v2/datasets/stock-price-limit-daily
        as_of: client. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('stock_price_limit_daily', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def stock_split_par_value_events(self, *, start: Optional[str] = None, end: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Stock Split / Par Value Events (除權息 / 面額變動) -- tier=free, status=active.

        Route: /v2/datasets/stock-split-par-value-events
        as_of: unsupported. data_gaps: server. pagination: limit only.
        Runs without an API key on the demo symbols.

        PIT note: no knowledge axis declared

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('stock_split_par_value_events', start=start, end=end, limit=limit, raw=raw, **extra)

    def subsidiary_investment(self, *, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """轉投資/子公司 -- tier=developer, status=active.

        Grain: one row per (parent_ticker, invested_entity).
        Route: /v2/datasets/subsidiary-investment
        as_of: unsupported. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: route accepts as_of but describe_dataset declares no knowledge
        axis and point_in_time_safe=false; SDK refuses as_of
        """
        return self.dataset('subsidiary_investment', limit=limit, raw=raw, **extra)

    def taifex_atm_iv(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """台指ATM隱含波動率 -- tier=max, status=active.

        Grain: one row per (trade_date).
        Route: /v2/datasets/taifex-atm-iv
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('taifex_atm_iv', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def taifex_final_settlement(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """期交所最後結算價 -- tier=max, status=active.

        Grain: one row per (contract, settlement_date).
        Route: /v2/datasets/futures-final-settlement
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'contract')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('taifex_final_settlement', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def taifex_options_delta(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """選擇權每日Delta -- tier=max, status=active.

        Grain: one row per (contract, call_put, contract_month_week, strike_price, trade_date).
        Route: /v2/datasets/taifex-options-delta
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'contract')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('taifex_options_delta', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def taifex_options_settlement_price(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """TAIFEX Options Settlement Price (選擇權每日結算價) -- tier=max, status=active.

        Route: /v2/datasets/taifex-options-settlement-price
        as_of: client. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'contract_code')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('taifex_options_settlement_price', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def taifex_put_call_ratio(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """選擇權Put/Call Ratio -- tier=max, status=active.

        Grain: one row per (trade_date).
        Route: /v2/datasets/taifex-put-call-ratio
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('taifex_put_call_ratio', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def tax_business_registration(self, *, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Business Registration (商業登記) -- tier=developer, status=active.

        Route: /v2/datasets/tax-business-registration
        as_of: server. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).
        """
        return self.dataset('tax_business_registration', as_of=as_of, limit=limit, raw=raw, **extra)

    def technical_indicators(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """技術指標 -- tier=max, status=active.

        Grain: one row per (ticker, trade_date, market, indicator_basis).
        Route: /v2/datasets/technical-indicators
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('technical_indicators', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def tpex_daily_price(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """TPEx Daily Price -- tier=free, status=active.

        Route: /v2/datasets/tpex-daily-price
        as_of: client. data_gaps: not on this route. pagination: limit only.

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('tpex_daily_price', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def trading_calendar(self, *, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """交易日曆 -- tier=free, status=active.

        Grain: one row per (trade_date, market).
        Route: /v2/datasets/trading-calendar
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.

        Args:
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('trading_calendar', start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def trading_rules_reference(self, *, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """交易制度沿革表 -- tier=free, status=active.

        Grain: one row per (rule_domain, rule_key, effective_date).
        Route: /v2/datasets/trading-rules-reference
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.
        """
        return self.dataset('trading_rules_reference', as_of=as_of, limit=limit, raw=raw, **extra)

    def twse_daily_price(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """TWSE Daily Price -- tier=free, status=active.

        Route: /v2/datasets/twse-daily-price
        as_of: client. data_gaps: not on this route. pagination: limit only.
        Runs without an API key on the demo symbols.

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('twse_daily_price', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def valuation_core_daily(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """Valuation Core Daily -- tier=pro, status=active.

        Route: /v2/datasets/valuation-core-daily
        as_of: client. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        Args:
            ticker: security id (sent as 'ticker')
            start: sent as 'date_from'
            end: sent as 'date_to'
        """
        return self.dataset('valuation_core_daily', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def valuation_data(self, *, ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """估值 PER/PBR/殖利率 -- tier=free, status=active.

        Grain: one row per (ticker, trade_date, market).
        Route: /v2/datasets/valuation-data
        as_of: client_unverified. data_gaps: server. pagination: limit only.
        Requires an API key (measured: 401 without one).

        PIT note: knowledge field 'trade_date' declared but absent from the
        published schema; SDK verifies at runtime

        Args:
            ticker: security id (sent as 'symbol')
            start: sent as 'start_date'
            end: sent as 'end_date'
        """
        return self.dataset('valuation_data', ticker=ticker, start=start, end=end, as_of=as_of, limit=limit, raw=raw, **extra)

    def warrants_reference(self, *, ticker: Optional[str] = None, as_of: Optional[str] = None, limit: Optional[int] = None, raw: bool = False, **extra: Any) -> Any:
        """權證參考資料 -- tier=free, status=active.

        Route: /v2/datasets/warrants-reference
        as_of: client. data_gaps: server. pagination: limit only.
        Runs without an API key on the demo symbols.

        Args:
            ticker: security id (sent as 'issuer')
        """
        return self.dataset('warrants_reference', ticker=ticker, as_of=as_of, limit=limit, raw=raw, **extra)

