# Changelog

## 0.2.0 — unreleased

First release under Apache-2.0. 0.1.0 remains MIT; the relicence applies from
0.2.0 onward and was made by the copyright holder.

Same distribution (`twmarketdata`) and same import name (`twmd`), so
`pip install -U twmarketdata` is the whole upgrade. **Everything 0.1.0 exported
still resolves and still works**, now emitting `DeprecationWarning` naming the
replacement. See "Upgrading from 0.1.0" in the README.

### Added

- **All 82 sellable datasets get a named method**, generated from the live API's
  own registry so none can be silently missed. Plus `Client.dataset()` as a
  generic escape hatch and `twmd.capabilities(name)` so limits are discoverable
  without trial and error.
- **Uniform parameters.** The API spells the security identifier seven ways and
  date bounds five ways; the SDK takes `ticker=`, `start=`, `end=` everywhere
  and translates per route. Routes keyed by something that is not a stock
  ticker (13 of them — `issuer`, `cb_id`, `contract`, `index_code`) also accept
  their native name, so `issuer="…"` reads correctly instead of a stock code
  being sent as an issuer code.
- **Point-in-time with five states**, decided per dataset and visible in
  `capabilities()`: `server` (16), `client` (45), `client_unsafe` (8),
  `client_unverified` (5), `unsupported` (8). The last two categories *refuse*
  `as_of` rather than returning a frame that merely looks replayed.
- **`knowledge_date` support.** When the API supplies that column it outranks
  the declared knowledge field, and `kd_imputed=true` raises
  `ImputedKnowledgeDateWarning` — an imputed date is derived from a statutory
  filing deadline, not observed from an announcement, and is never presented as
  observed. Tracks `WORKORDER_API_expose_knowledge_date`.
- **Gaps with a stated source.** `Meta.gaps_source` is `server` (22 routes),
  `client_derived` (opt-in, computed against `trading_calendar`), `unsupported`,
  or `unknown`. Nothing is zero-filled, forward-filled or interpolated.
- **Truncation is visible.** Only 9 of 82 routes take `offset`;
  `Meta.truncated` says when a result was cut off.
- **`twmd.compat.finmind`** — FinMind-shaped calls served by TWMD, every mapping
  graded A/B/C/D. D-grade and unverified mappings raise `NotMappedError` instead
  of returning an empty frame, since an empty frame reads as "your query matched
  nothing" rather than "this does not exist here".
- **`TwmdFrame`**, a `pandas.DataFrame` subclass carrying `Meta` on `.twmd`.
  Without pandas the SDK returns `list[dict]` and still works.
- Free-tier mode with no API key for five demo symbols and the 16 datasets
  *measured* to serve them.
- `py.typed`, full annotations, generated `.pyi` for the 82 methods.

### Changed from 0.1.0

- `base_url` now defaults to `https://api.twmarketdata.com/v2`. 0.1.0 pointed at
  `https://twmarketdata.com`, which has been retired and returns
  **HTTP 410 `endpoint_retired`** — every 0.1.0 call fails today.
- Error classification follows the FRICTION-01 R2 contract (flat
  `{"error", "message"}` envelope; 402 entitlement, 403 authenticated-but-
  forbidden, 429 quota), plus `410 endpoint_retired`, plus
  **`403 temporarily_blocked` classified as a rate limit** rather than a
  permissions failure.
- `requests` replaces `httpx`. The 0.1.0 `transport=` parameter took an
  `httpx.BaseTransport`; pass `session=` a `requests.Session` instead.
- Default `max_concurrency` is 2. Four concurrent requests tripped a block that
  persisted for tens of minutes during measurement.
- The access tables (`OPEN_DATASETS` and friends) were re-measured. 0.1.0
  recorded 2 key-free datasets from a probe on 2026-07-21; a full 82-route sweep
  plus a non-demo-ticker sweep found 15 open and the same 3 sample-only. Names,
  semantics and return types unchanged.
- `iter_pages` / `get_all` stop when the server ignores `offset`. Measured on
  `index-constituents`, where offsets 0, 3 and 6 returned identical pages;
  continuing would append duplicates and present them as a full history.

### Deprecated

Still working, warning on use: `Client.get_dataset` / `get_all` / `iter_pages` /
`list_datasets` / `is_key_free`, the `twmd.access` and `twmd.frames` modules,
`to_dataframe`, `TWMarketDataClient`, and the `Twmd*Error` names
(`TwmdAPIError`, `TwmdPaymentRequired` with its `payment` / `price` /
`credits_url` / `purchase_hint` accessors, `TwmdRateLimitError`,
`TwmdTransportError`, `TwmdNotFoundError`, `TwmdValidationError`).

### Found while recording paid-tier responses

- **`limit` is capped per route, at five different values** (100 / 500 / 1000 /
  2000 / 5000); 56 of 82 are not 5000. Worse, the declared cap is not always the
  enforced one — `margin_system_stats` declares 5000 and rejects anything over
  1000. The SDK clamps from the registry, and if a 422 still names a lower cap
  it retries once at that value and says so.
- **`knowledge_date` is live on the four fundamentals** (`income_statement`,
  `balance_sheet`, `cash_flow_statement`, `financial_ratios`) — and every row
  carries `kd_imputed=true` with `kd_source=statutory_deadline`. Not one
  observed announcement timestamp. `as_of` on these datasets now warns even in
  server mode, so nobody running a server-side PIT backtest is the only party
  not told. Phase 1 then reached `monthly_revenue` as well.
- **`client_unsafe` datasets are probed, not refused outright.** The registry is
  a snapshot and the API is not: `knowledge_date` is rolling out dataset by
  dataset. Refusing before making the request left the refusal message's own
  promise ("if the API now returns a knowledge_date, this restriction lifts")
  permanently false. These datasets now cost one request before refusing, and
  when the response carries a real knowledge_date the query is answered with the
  imputed-date warning. Verified live on `monthly_revenue`: `as_of=2026-06-30`
  drops the June figure, whose knowledge date is 2026-07-10. Datasets with no
  declared knowledge axis at all still refuse without a request.
- **`report_date` is null on every income-statement row**, confirming the
  upstream writer gap on live paid data — which is why the knowledge date has to
  be imputed in the first place.
- **Rows sit at `envelope.data` on 9 datasets**, not just `price_enhanced`.
  Before the nested lookup they all returned empty frames.
- **`price_enhanced` really does serve adjustment factors, not OHLCV** —
  `event_type`, `factor`, `pre_event_close`, `reference_price`. `close` never
  appears, though the dataset contract declares it required.
- **A `max` plan does not include `developer`-tier datasets** (10 of them return
  402). The tiers are not one ladder.
- `400` / `422` now raise `ValidationError` instead of a generic error, keeping
  the server's wording — it is the only thing that names the offending field.

### Compat mappings settled against live rows

Seven candidates were checked column by column. Three were promoted, and two
were **withdrawn** — evidence that a substitution would mislead is as decisive
as evidence that it works:

- `taiwan_stock_market_value` → `valuation_core_daily` — **promoted**;
  `market_cap` is there, alongside `shares_outstanding` and the ratios.
- `taiwan_stock_convertible_bond_put_provision` → `convertible_bond_overview` —
  **promoted**; `put_start_date` / `put_end_date` / `put_price` all present.
- `taiwan_stock_news` → `company_news` — **kept, now precisely described**:
  headline, timestamp and link only. `metadata_only=true` and `summary=null`, so
  there is no article body to analyse, and the source is MOPS announcements
  rather than a press feed.
- `taiwan_stock_day_trading` → **withdrawn to D**. `price_move_context` carries
  `day_trade_ratio` but only has rows on large-move days, so serving it would
  return a silently biased sample rather than day-trading statistics.
- `taiwan_stock_convertible_bond_daily` → **withdrawn to D**.
  `convertible_bond_overview` has no OHLC at all, only `reference_price` —
  a different quantity from a traded price.

### Known limitations

- **Compat column names are TWMD's.** Parameter names are mirrored; response
  column names are not. Mirroring them would require comparing live responses
  from another service, which this project does not do. A `stock_id` alias is
  added where an identifier column exists.
- **Two compat mappings remain withheld** as unverified, down from nine. Both
  are blocked on access rather than on judgement: `etf_holdings` is
  developer-tier and returned 402 to a max key *and* to a developer key, and
  `taiwan_stock_10year` has no candidate dataset at all. They raise
  `NotMappedError` naming what is missing.
- **B-grade mappings without an implemented reshape refuse** and point at the
  native method, rather than returning the wrong shape.
- Paid-tier behaviour is covered by 63 recorded cassettes (2026-08-12, restricted
  key since deleted, auth headers redacted and asserted so by a test). Seven
  compat mappings remain unverified because their datasets are `developer`-tier
  and a `max` key does not reach them.
- Three datasets declared `tier=free` return 401 in practice
  (`valuation_data`, `issuer_profiles`, `industry_index`), so `tier` alone does
  not tell you what runs without a key. Use `twmd.runnable_without_key()`.

## 0.1.0 — 2026-07-21

Initial release (MIT). Retrieval-only client with `get_dataset`, pagination
helpers, an access-tier module and DataFrame conversion.
