"""FinMind -> TWMD interop mapping table (source of truth for mapping/finmind_map.csv).

PROVENANCE
  FinMind side : signature introspection of the installed open-source package
                 `FinMind` v2.0.7, performed 2026-08-12 (tools/introspect_finmind.py).
                 Method names / parameter names only. The FinMind service was NOT
                 called, no credentials were used, and no FinMind source code is
                 copied into or redistributed by this project.
  TWMD side    : twmd.describe_dataset (MCP, 2026-08-12) + GET /v2/datasets +
                 GET /openapi.json + GET /v2/datasets/{key}/schema, all 2026-08-12.

TIERS
  A  one_to_one   same grain + same meaning; field renames only.
  B  transformed  same underlying fact, different shape/grain/units; compat reshapes.
  C  substituted  no same-named equivalent; TWMD covers it differently. Compat returns
                  data and emits CompatSubstitutionWarning explaining the difference.
  D  unavailable  TWMD has no equivalent inside the 82 sellable datasets. Compat raises
                  NotMappedError. It never returns an empty frame to fake success.
  E  twmd_only    present in TWMD, no corresponding entry found in the introspected
                  FinMind v2.0.7 surface (102 DataLoader methods / 105 dataset enum
                  entries). Stated as an observation about that introspected surface,
                  not as a claim about the product as a whole.

CONFIDENCE
  high    TWMD dataset semantics read from describe_dataset AND field list from the
          published schema; mapping is mechanical.
  medium  semantics read, but shape/field equivalence still needs a live row comparison
          (blocked on the restricted test key).
  low     mapping is a hypothesis; MUST be confirmed against live rows before it ships.

Every row is re-checkable: rerun tools/introspect_finmind.py and tools/build_mapping.py.
"""

FINMIND_VERSION = "2.0.7"
INTROSPECTED_ON = "2026-08-12"

# (finmind_method, finmind_dataset_enum, tier, twmd_dataset(s), confidence, note)
MAPPINGS = [
    # ---------------------------------------------------------------- prices
    ("taiwan_stock_daily", "TaiwanStockPrice", "A", "twse_daily_price+tpex_daily_price", "high",
     "L3 c.daily_price() merges both boards and adds a `market` column; no silent cross-board dedup."),
    ("taiwan_stock_daily_adj", "TaiwanStockPriceAdj", "C", "price_enhanced+twse_daily_price", "medium",
     "TWMD publishes adjustment FACTORS rather than a pre-adjusted series; compat applies the factors "
     "and marks the result adjusted=True with the factor version used."),
    ("taiwan_stock_weekly", "TaiwanStockWeekPrice", "C", "twse_daily_price+tpex_daily_price", "high",
     "No native weekly series; compat resamples daily bars and flags derived=True. Volume sums, OHLC "
     "from first/max/min/last within the trading week."),
    ("taiwan_stock_monthly", "TaiwanStockMonthPrice", "C", "twse_daily_price+tpex_daily_price", "high",
     "Same as weekly: resampled from daily, derived=True."),
    ("taiwan_stock_total_return_index", "TaiwanStockTotalReturnIndex", "A", "return_index_daily", "high",
     "Dividend-reinvested index. Correct total-return backtest benchmark."),
    ("taiwan_stock_price_limit", "TaiwanStockPriceLimit", "A", "stock_price_limit_daily", "medium",
     "tier=max. Field equivalence unverified until the test key lands."),
    ("taiwan_stock_market_value_weight", "TaiwanStockMarketValueWeight", "A", "market_value_weight", "high", ""),
    ("taiwan_stock_market_value", "TaiwanStockMarketValue", "C", "valuation_core_daily", "high",
     "Confirmed on live rows 2026-08-12: valuation_core_daily carries market_cap, alongside "
     "shares_outstanding, close, pe, pb, ps, dividend_yield and book_value_per_share. Market "
     "cap is served inside a broader daily valuation table rather than as a series of its own."),
    ("taiwan_stock_kbar", "TaiwanStockKBar", "D", "", "high", "Intraday K-bars: no intraday dataset among the 82."),
    ("taiwan_stock_tick", "TaiwanStockPriceTick", "D", "", "high", "Tick data: not in the 82."),
    ("taiwan_stock_tick_snapshot", "taiwan_stock_tick_snapshot", "D", "", "high", "Realtime snapshot: not in the 82."),
    ("taiwan_stock_book_and_trade", "TaiwanStockStatisticsOfOrderBookAndTrade", "D", "", "high", "Order-book stats: not in the 82."),
    ("(price_bid_ask)", "TaiwanStockPriceBidAsk", "D", "", "high", "Best bid/ask: not in the 82."),
    ("taiwan_stock_every5seconds_index", "TaiwanStockEvery5SecondsIndex", "D", "", "high", "5-second index: not in the 82."),
    ("(various_indicators_5s)", "TaiwanVariousIndicators5Seconds", "D", "", "high", "Not in the 82."),
    ("tse", "-", "D", "", "medium", "Intraday TSE aggregate; not in the 82."),

    # ------------------------------------------------------- indices / universe
    ("taiwan_stock_info", "TaiwanStockInfo", "A", "security_master", "high",
     "TWMD carries list_date/delist_date, so a delisting-aware universe is constructible."),
    ("taiwan_stock_info_with_warrant", "TaiwanStockInfoWithWarrant", "B", "security_master+warrants_reference", "medium",
     "Compat concatenates the equity master with the warrant reference table."),
    ("taiwan_stock_info_with_warrant_summary", "TaiwanStockInfoWithWarrantSummary", "C", "warrants_reference", "medium",
     "Confirmed against live rows 2026-08-12: per-warrant reference records "
     "(warrant_code, warrant_type, underlying_ticker, issuer, strike_price, "
     "exercise_ratio, exercise_style, settlement_style, expiry_date, listing_date), "
     "NOT a pre-aggregated summary -- aggregate client-side if you need one. Note the "
     "route is keyed by `issuer`, so filtering by underlying stock happens client-side "
     "on underlying_ticker."),
    ("taiwan_stock_trading_date", "TaiwanStockTradingDate", "A", "trading_calendar", "high",
     "PIT note: absence of future rows means 'no evidence yet', not 'market closed'."),
    ("taiwan_stock_delisting", "TaiwanStockDelisting", "B", "stock_delisting_lifecycle", "medium",
     "TWMD models the full lifecycle (multiple stages), not a single delisting date."),
    ("taiwan_stock_suspended", "TaiwanStockSuspended", "C", "stock_delisting_lifecycle", "medium",
     "Confirmed against live rows 2026-08-12: the dataset carries suspension_date, "
     "event_type, announcement_date, delisting_date and reason_summary, so suspension "
     "IS represented. Narrower than the source though -- these are suspensions within "
     "the delisting lifecycle, not every trading halt."),

    # --------------------------------------------------------- fundamentals
    ("taiwan_stock_month_revenue", "TaiwanStockMonthRevenue", "A", "monthly_revenue", "high",
     "PIT WARNING: knowledge_time_field is as_of_date = the revenue PERIOD, not the announcement date. "
     "announcement_date was NULL for 2330 in the 2026-08-12 free-tier probe, so as_of on this dataset "
     "raises PITDataMissingWarning instead of silently passing."),
    ("taiwan_stock_financial_statement", "TaiwanStockFinancialStatements", "B", "income_statement", "high",
     "FinMind returns a long (type, value) row per line item; TWMD is wide (revenue, operating_income, "
     "net_income, eps). Compat melts wide->long to preserve the caller's shape."),
    ("taiwan_stock_balance_sheet", "TaiwanStockBalanceSheet", "B", "balance_sheet", "high", "Same wide->long reshape."),
    ("taiwan_stock_cash_flows_statement", "TaiwanStockCashFlowsStatement", "B", "cash_flow_statement", "high", "Same wide->long reshape."),
    ("taiwan_stock_per_pbr", "TaiwanStockPER", "A", "valuation_data", "high", "PER / PBR / dividend yield, PIT-safe on trade_date."),
    ("taiwan_stock_dividend", "TaiwanStockDividend", "B", "dividends", "medium",
     "TWMD registry_status=partial. Compat surfaces status='partial' in Meta."),
    ("taiwan_stock_dividend_result", "TaiwanStockDividendResult", "C", "corporate_actions", "medium",
     "TWMD models ex-rights/ex-dividend REFERENCE PRICES; registry_status=partial."),

    # ---------------------------------------------------------------- chips
    ("taiwan_stock_institutional_investors", "TaiwanStockInstitutionalInvestorsBuySell", "C", "institutional_flow", "high",
     "GRAIN LOSS: FinMind splits by investor type (foreign / trust / dealer); TWMD institutional_flow is "
     "the three-institution NET TOTAL. Compat returns the total with investor type set to 'total' and "
     "warns. Per-type breakdown is not in the 82."),
    ("taiwan_stock_institutional_investors_wide", "TaiwanStockInstitutionalInvestorsBuySellWide", "C", "institutional_flow", "high", "Same grain loss as above."),
    ("taiwan_stock_institutional_investors_total", "TaiwanStockTotalInstitutionalInvestors", "D", "", "high",
     "A market-level aggregate route exists in the OpenAPI (institutional-flow-market-aggregate) but is "
     "NOT in the 82 sellable set, so compat will not silently reach for it."),
    ("taiwan_stock_margin_purchase_short_sale", "TaiwanStockMarginPurchaseShortSale", "A", "margin_short", "high", ""),
    ("taiwan_stock_margin_purchase_short_sale_total", "TaiwanStockTotalMarginPurchaseShortSale", "A", "margin_short_total", "medium", ""),
    ("taiwan_stock_margin_maintenance", "TaiwanStockMarginMaintenance", "C", "margin_system_stats", "high",
     "HONEST GAP: margin_system_stats.maintenance_ratio is documented NULL (not loaded). Compat returns "
     "the column as NA and records it in data_gaps rather than substituting a computed proxy."),
    ("taiwan_total_exchange_margin_maintenance", "TaiwanTotalExchangeMarginMaintenance", "C", "margin_system_stats", "high", "Same NULL maintenance_ratio caveat."),
    ("taiwan_stock_securities_lending", "TaiwanStockSecuritiesLending", "A", "securities_lending", "high", ""),
    ("taiwan_daily_short_sale_balances", "TaiwanDailyShortSaleBalances", "B", "short_sale_balance_control", "medium",
     "TWMD carries both margin-short (ms_*) and SBL (sbl_*) legs plus next-day limits; wider than the source."),
    ("taiwan_stock_margin_short_sale_suspension", "TaiwanStockMarginShortSaleSuspension", "C", "margin_short_cover_date", "medium",
     "PIT WARNING: cover_date is a FUTURE event date and the table carries no announcement column, so "
     "as_of is rejected (PointInTimeUnavailable) rather than answered with a look-ahead."),
    ("taiwan_stock_shareholding", "TaiwanStockShareholding", "A", "foreign_holding", "high", "Foreign + mainland-China holding pct."),
    ("taiwan_stock_holding_shares_per", "TaiwanStockHoldingSharesPer", "C", "shareholding_concentration", "high",
     "COVERAGE WARNING: TWMD derives >=400 / >=1000 lot tiers rather than republishing the raw 15-tier "
     "table, AND the series accumulates forward from 2026-08 (the source keeps no archive). Earlier "
     "weeks are unobtainable, not missing. Compat states this in data_gaps."),
    ("taiwan_stock_block_trade", "TaiwanStockBlockTrade", "A", "block_trade_daily", "medium", "tier=developer."),
    ("taiwan_stock_day_trading", "TaiwanStockDayTrading", "D", "", "high",
     "Withdrawn on evidence 2026-08-12. price_move_context does carry day_trade_ratio, but it only "
     "has rows on days a stock made a large move (magnitude_bucket, hit_track, threshold_version). "
     "Serving that for a day-trading query would return a silently biased subset -- big-move days "
     "only -- which is worse than returning nothing. No unbiased day-trading table exists in the 82."),
    ("taiwan_stock_day_trading_borrowing_fee_rate", "TaiwanStockDayTradingBorrowingFeeRate", "D", "", "high", "Not in the 82."),
    ("taiwan_stock_loan_collateral_balance", "TaiwanStockLoanCollateralBalance", "D", "", "high", "Not in the 82."),
    ("taiwan_stock_government_bank_buy_sell", "TaiwanStockGovernmentBankBuySell", "D", "", "high", "Eight-bank buy/sell: not in the 82."),
    ("taiwan_stock_trading_daily_report", "TaiwanStockTradingDailyReport", "D", "", "high",
     "Broker-branch daily flow is not in the 82. TWMD has the branch ROSTER "
     "(broker_branch_reference / securities_firm_master) but not branch-level buy/sell."),
    ("taiwan_stock_trading_daily_report_secid_agg", "TaiwanStockTradingDailyReportSecIdAgg", "D", "", "high", "Same as above."),
    ("taiwan_stock_warrant_trading_daily_report", "TaiwanStockWarrantTradingDailyReport", "D", "", "high", "Same as above."),
    ("taiwan_securities_trader_info", "TaiwanSecuritiesTraderInfo", "B", "securities_firm_master+broker_branch_reference", "high",
     "Firm master plus monthly branch-roster snapshot."),

    # --------------------------------------------------------------- events
    ("taiwan_stock_day_trading_suspension", "TaiwanStockDayTradingSuspension", "A", "day_trading_suspension", "high",
     "PIT WARNING: suspension_start_date is a future effective date and no announcement column exists; "
     "as_of is rejected."),
    ("taiwan_stock_disposition_securities_period", "TaiwanStockDispositionSecuritiesPeriod", "B", "attention_disposal_events", "high",
     "TWMD folds attention and disposition into one event table. PIT WARNING: event_date is the "
     "EFFECTIVE date and the announcement precedes it; as_of is rejected."),
    ("taiwan_stock_capital_reduction_reference_price", "TaiwanStockCapitalReductionReferencePrice", "B", "capital_formation_events", "medium",
     "TWMD covers both cash capital increase schedules and capital reduction history."),
    ("taiwan_stock_par_value_change", "TaiwanStockParValueChange", "B", "stock_split_par_value_events", "medium", ""),
    ("taiwan_stock_split_price", "TaiwanStockSplitPrice", "B", "stock_split_par_value_events", "medium", ""),
    ("taiwan_stock_news", "TaiwanStockNews", "C", "company_news", "high",
     "Characterised on live rows 2026-08-12: headline + published_at + content_url only. "
     "metadata_only=true and summary=null, so NO article body is served -- sentiment work on news "
     "text will find nothing. source_name=mops_official, i.e. MOPS announcements rather than a "
     "press feed, and source_attribution_required=true. Querying by ticker returned no rows for "
     "2330 in the sampled window; the feed is not densely ticker-indexed."),
    ("taiwan_stock_industry_chain", "TaiwanStockIndustryChain", "B", "industry_chain", "high",
     "PIT WARNING: capture_date is TWMD's OBSERVATION date, not the disclosure date, and history is "
     "not backfilled; point_in_time_safe=false."),
    ("taiwan_stock_industry_chain_money_flow", "TaiwanStockIndustryChainMoneyFlow", "D", "", "high", "Not in the 82."),

    # -------------------------------------------------------------- ETF / fund
    ("taiwan_stock_active_etf_info", "TaiwanStockActiveETFInfo", "C", "fund_etf_metadata", "medium",
     "TWMD metadata spans funds/ETFs generally rather than active ETFs specifically."),
    ("taiwan_stock_active_etf_holding", "TaiwanStockActiveETFHolding", "C", "etf_holdings", "medium", "tier=developer."),
    ("taiwan_stock_active_etf_holding_change", "TaiwanStockActiveETFHoldingChange", "C", "etf_holdings", "low",
     "STILL UNVERIFIED: etf_holdings is developer-tier and returned 402 for both the max key and "
     "the developer key issued on 2026-08-12, so its columns have never been observed. A change "
     "series would in any case have to be diffed client-side from consecutive snapshots."),

    # ---------------------------------------------------- convertible bonds
    ("taiwan_stock_convertible_bond_info", "TaiwanStockConvertibleBondInfo", "A", "bond_convertible_reference", "high", "Includes matured bonds."),
    ("taiwan_stock_convertible_bond_daily_overview", "TaiwanStockConvertibleBondDailyOverview", "A", "convertible_bond_overview", "high", ""),
    ("taiwan_stock_convertible_bond_institutional_investors", "TaiwanStockConvertibleBondInstitutionalInvestors", "A", "convertible_bond_institutional", "high", ""),
    ("taiwan_stock_convertible_bond_monthly_analysis", "TaiwanStockConvertibleBondMonthlyAnalysis", "B", "convertible_bond_monthly", "medium", "TDCC custody monthly."),
    ("taiwan_stock_convertible_bond_daily", "TaiwanStockConvertibleBondDaily", "D", "", "high",
     "Withdrawn on evidence 2026-08-12. convertible_bond_overview has no open/high/low/close at "
     "all -- only reference_price, plus terms. Passing a reference price off as a daily traded "
     "price is a different quantity and would corrupt any analysis built on it."),
    ("taiwan_stock_convertible_bond_put_provision", "TaiwanStockConvertibleBondPutProvision", "C", "convertible_bond_overview", "high",
     "Confirmed on live rows 2026-08-12: put_start_date, put_end_date and put_price are all "
     "present, along with the redemption_* and conversion_* terms. The provisions live in the "
     "overview board rather than a table of their own, so filter the columns you need."),
    ("taiwan_asset_swap_fixed_income_daily", "TaiwanAssetSwapFixedIncomeDaily", "D", "", "high", "Not in the 82."),
    ("taiwan_asset_swap_option_daily", "TaiwanAssetSwapOptionDaily", "D", "", "high", "Not in the 82."),

    # ------------------------------------------------------------ derivatives
    ("taiwan_futures_daily", "TaiwanFuturesDaily", "B", "derivatives_market", "medium", "tier=max."),
    ("taiwan_option_daily", "TaiwanOptionDaily", "A", "options_daily_taifex", "medium", "tier=max."),
    ("taiwan_futures_final_settlement_price", "TaiwanFuturesFinalSettlementPrice", "A", "taifex_final_settlement", "high",
     "Filter product_type=futures. Route is /futures-final-settlement (NOT kebab(dataset_key))."),
    ("taiwan_option_final_settlement_price", "TaiwanOptionFinalSettlementPrice", "B", "taifex_final_settlement", "medium",
     "Filter product_type=option. A separate /option-final-settlement route exists but is not in the 82."),
    ("taiwan_option_vix", "TaiwanOptionVix", "C", "taifex_atm_iv", "high",
     "NOT the official VIX. TWMD derives ATM implied volatility via Black-Scholes from official TXO "
     "prices and TAIEX spot. Compat labels the column atm_iv_derived and warns."),
    ("taiwan_futures_institutional_investors", "TaiwanFuturesInstitutionalInvestors", "C", "futures_daily_context", "medium",
     "Only inst_net_oi_foreign is carried, and it is NULL before 2023-07."),
    ("taiwan_option_institutional_investors", "TaiwanOptionInstitutionalInvestors", "D", "", "high", "Not in the 82."),
    ("taiwan_futures_institutional_investors_after_hours", "TaiwanFuturesInstitutionalInvestorsAfterHours", "D", "", "high", "Not in the 82."),
    ("taiwan_option_institutional_investors_after_hours", "TaiwanOptionInstitutionalInvestorsAfterHours", "D", "", "high", "Not in the 82."),
    ("taiwan_futures_open_interest_large_traders", "TaiwanFuturesOpenInterestLargeTraders", "D", "", "high", "Not in the 82."),
    ("taiwan_option_open_interest_large_traders", "TaiwanOptionOpenInterestLargeTraders", "D", "", "high", "Not in the 82."),
    ("taiwan_futures_dealer_trading_volume_daily", "TaiwanFuturesDealerTradingVolumeDaily", "D", "", "high", "Not in the 82."),
    ("taiwan_option_dealer_trading_volume_daily", "TaiwanOptionDealerTradingVolumeDaily", "D", "", "high", "Not in the 82."),
    ("taiwan_futures_tick", "TaiwanFuturesTick", "D", "", "high", "Tick data: not in the 82."),
    ("taiwan_option_tick", "TaiwanOptionTick", "D", "", "high", "Tick data: not in the 82."),
    ("taiwan_futures_spread_tick", "TaiwanFuturesSpreadTick", "D", "", "high", "Not in the 82."),
    ("taiwan_futures_spread_trading", "TaiwanFuturesSpreadTrading", "D", "", "high", "Not in the 82."),
    ("taiwan_futopt_daily_info", "TaiwanFutOptDailyInfo", "D", "", "medium", "Contract reference listing: not in the 82."),
    ("taiwan_futopt_tick_info", "TaiwanFutOptTickInfo", "D", "", "high", "Not in the 82."),
    ("taiwan_futopt_tick_realtime", "TaiwanFutOptTick", "D", "", "high", "Realtime: not in the 82."),
    ("taiwan_futures_snapshot", "taiwan_futures_snapshot", "D", "", "high", "Realtime: not in the 82."),
    ("taiwan_options_snapshot", "taiwan_options_snapshot", "D", "", "high", "Realtime: not in the 82."),

    # ---------------------------------------------------------------- macro
    ("taiwan_business_indicator", "TaiwanBusinessIndicator", "D", "", "high",
     "A /business-indicator-monthly route exists in the OpenAPI but is not in the 82 sellable set."),
    ("(exchange_rate)", "TaiwanExchangeRate", "C", "competitor_fx", "high",
     "TWMD covers USD/TWD plus the JPY/KRW/CNY export-competitor crosses, not a full FX board."),
    ("(exchange_rate_global)", "ExchangeRate", "D", "", "high", "Global FX board: not in the 82."),
    ("(government_bonds_yield)", "GovernmentBondsYield", "B", "bond_yield_curve", "medium",
     "Taiwan central-government bond curve by tenor. tier=max."),
    ("(interest_rate)", "InterestRate", "C", "interest_rate_snapshots", "medium", "tier=developer."),
    ("taiwan_stock_10year", "TaiwanStock10Year", "D", "", "low",
     "Semantics of the source series not established from the signature alone; deliberately left "
     "unmapped rather than guessed."),
    ("(us_stock_info)", "USStockInfo", "D", "", "high", "Non-Taiwan. TWMD is a Taiwan-market provider."),
    ("us_stock_price", "USStockPrice", "D", "", "high", "Non-Taiwan."),
    ("(us_stock_price_minute)", "USStockPriceMinute", "D", "", "high", "Non-Taiwan."),
    ("(europe_stock_info)", "EuropeStockInfo", "D", "", "high", "Non-Taiwan."),
    ("(japan_stock_info)", "JapanStockInfo", "D", "", "high", "Non-Taiwan."),
    ("(uk_stock_info)", "UKStockInfo", "D", "", "high", "Non-Taiwan."),
    ("(gold_price)", "GoldPrice", "D", "", "high", "Commodity: not in the 82."),
    ("(crude_oil_prices)", "CrudeOilPrices", "D", "", "high", "Commodity: not in the 82."),
    ("cnn_fear_greed_index", "CnnFearGreedIndex", "D", "", "high", "Third-party sentiment index: not in the 82."),
]

# TWMD datasets with no corresponding entry in the introspected FinMind v2.0.7 surface.
# Neutral observation about that surface; listed so users can see what they gain, not as a knock.
TWMD_ONLY = [
    ("financial_ratios", "Quarterly ROE/ROA/margins/leverage precomputed from the three statements."),
    ("market_index", "Daily TAIEX / OTC / sector index OHLC. The introspected surface exposes a total-return "
                     "index and intraday index series, but no daily price-index dataset."),
    ("technical_indicators", "Precomputed MA/RSI/MACD with an explicit indicator_basis (adjusted vs unadjusted)."),
    ("valuation_core_daily", "Daily valuation core series."),
    ("market_breadth", "Market-level breadth."),
    ("market_overview_snapshots", "Market overview snapshots."),
    ("industry_index", "Industry/sector index daily (registry_status=planned)."),
    ("industry_index_daily", "Industry index daily (registry_status=partial)."),
    ("index_constituents", "Index constituents."),
    ("limit_events", "One row per limit-up/limit-down lock, with era-aware limit bands and consecutive counts."),
    ("price_move_context", "Large-move context cards bundling the move with same-day chip and event context."),
    ("lending_utilization", "Lending balance over shares issued, with an explicit NULL-denominator note."),
    ("short_restriction_flags", "Per-ticker daily short-sale restriction state."),
    ("margin_system_stats", "Market-level margin/short system statistics."),
    ("major_event_taxonomy", "MOPS material announcements classified into an event taxonomy with rule version and confidence."),
    ("mops_major_event", "Structured MOPS material announcements with announcement timestamps."),
    ("investor_conference_calendar", "Investor conference calendar with the announcement date as the PIT axis."),
    ("capital_formation_events", "Capital increase/reduction events."),
    ("company_industry_exposures", "Derived industry exposure (current snapshot; as_of rejected by design)."),
    ("company_peer_groups", "Derived peer groups (current snapshot; as_of rejected by design)."),
    ("subsidiary_investment", "Parent/subsidiary holdings graph."),
    ("taifex_put_call_ratio", "Daily options put/call volume and OI ratios."),
    ("taifex_options_delta", "Per-series daily option delta."),
    ("taifex_options_settlement_price", "Daily options settlement prices."),
    ("futures_daily_context", "Futures basis, OI change, days-to-settlement in one row."),
    ("bond_convertible_reference", "Convertible bond reference master including matured issues."),
    ("customs_trade_monthly", "Official monthly customs trade statistics."),
    ("export_orders_monthly", "Official monthly export orders by commodity."),
    ("production_value_index_monthly", "Official monthly manufacturing production-value index."),
    ("macro_worldbank", "World Bank WDI (annual; source retro-revises, so explicitly not PIT)."),
    ("macro_global", "Global macro (enterprise tier, private beta)."),
    ("esg_ghg_carbon_disclosure", "GHG / carbon disclosure."),
    ("governance_t187ap33_l", "Chairman/GM duality governance flag."),
    ("tax_business_registration", "Business registration records."),
    ("issuer_classification", "Issuer classification."),
    ("issuer_profiles", "Issuer profiles."),
    ("trading_rules_reference", "Timeline of market microstructure rule changes, each with an official source URL."),
    ("stock_delisting_lifecycle", "Delisting lifecycle stages (survivorship-bias control)."),
]
