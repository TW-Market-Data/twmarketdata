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

### Known limitations

- **Compat column names are TWMD's.** Parameter names are mirrored; response
  column names are not. Mirroring them would require comparing live responses
  from another service, which this project does not do. A `stock_id` alias is
  added where an identifier column exists.
- **Seven compat mappings are withheld** as unverified. They raise
  `NotMappedError` naming the candidate dataset rather than shipping a guess.
- **B-grade mappings without an implemented reshape refuse** and point at the
  native method, rather than returning the wrong shape.
- Paid-tier behaviour is not yet covered by recorded cassettes; that work is
  gated on a restricted test key. `examples/03` and `examples/04` are written
  but marked *recorded pending test key* and have not been run against paid
  endpoints.
- Three datasets declared `tier=free` return 401 in practice
  (`valuation_data`, `issuer_profiles`, `industry_index`), so `tier` alone does
  not tell you what runs without a key. Use `twmd.runnable_without_key()`.

## 0.1.0 — 2026-07-21

Initial release (MIT). Retrieval-only client with `get_dataset`, pagination
helpers, an access-tier module and DataFrame conversion.
