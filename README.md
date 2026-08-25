# TWMD Python SDK

**TWMD = TW Market Data = [twmarketdata.com](https://twmarketdata.com)** — the official Python SDK for Taiwan market data.

```bash
pip install twmarketdata
```

```python
from twmd import Client

df = Client().daily_price("2330")     # TSMC daily OHLCV, no API key needed
```

That returns a `pandas.DataFrame`. No key, no signup, no config — the free tier serves five demo symbols so the example above runs as written.

> The distribution is `twmarketdata`; the import is `twmd`.

---

## Why this SDK exists

The REST API is not uniform. Across the 82 sellable datasets, the security identifier is spelled seven different ways, date bounds five different ways, `as_of` exists on 17 routes, `offset` on 9, and six routes are not the kebab-case of their dataset key. Response rows arrive under `rows`, `items`, or `data` depending on the dataset.

This SDK absorbs all of that, so you write `ticker=`, `start=`, `end=` everywhere and get one response shape back.

It also does something most market-data clients don't: **it tells you what it doesn't know.**

---

## Three things this SDK guarantees

### 1. Two lines to a DataFrame

Every one of the 82 sellable datasets has a named method, generated from the live API's own registry so none can be missed:

```python
from twmd import Client

c = Client()                                  # free tier
c.monthly_revenue(ticker="2330")              # 月營收
c.security_master(limit=10)                   # 證券主檔
c.trading_calendar(start="2026-01-01")        # 交易日曆
```

There's a generic escape hatch too, and a capability lookup so you never have to discover limits by trial and error:

```python
import twmd

c.dataset("monthly_revenue", ticker="2330", start="2024-01-01")

twmd.capabilities("monthly_revenue")
# {'tier': 'free', 'status': 'active', 'as_of': 'client_unsafe',
#  'point_in_time_safe': False, 'knowledge_time_field': 'as_of_date',
#  'pagination': 'limit_only', 'runnable_without_key': True, ...}
```

### 2. Point-in-time that refuses to lie

`as_of=` replays a dataset to what was knowable on a given date. The interesting part is what happens when it *can't*:

```python
c.balance_sheet(ticker="2330", as_of="2023-06-30")   # server-side replay

c.company_peer_groups(as_of="2023-06-30")
# raises PointInTimeUnavailable:
#   this dataset declares no knowledge-time axis, so there is no honest way to
#   replay it to a past date
```

That refusal is the feature. Take `monthly_revenue`: its declared `as_of_date` is the revenue **period**, not the announcement date — June revenue is disclosed in July. Filtering on it would mark June revenue as known on June 30, which is precisely the look-ahead `as_of` exists to prevent. So the SDK will not filter on that column.

It does not refuse blindly, though. The registry is a snapshot and the API is not, so for these datasets the SDK makes the request and looks: if the response carries a real server-supplied `knowledge_date`, that outranks the classification and the query is answered. `monthly_revenue` returns one as of 2026-08-12, so `as_of="2026-06-30"` now correctly drops the June figure (knowledge date 2026-07-10) and keeps May. When no such column comes back, the call raises — and says it checked.

Five states, one per dataset, all visible in `capabilities()`:

| state | datasets | behaviour |
|---|---|---|
| `server` | 16 | the route filters; passed straight through |
| `client` | 45 | PIT-safe, knowledge column published; filtered locally |
| `client_unsafe` | 8 | declared column isn't a disclosure date; **refused** unless you pass `as_of_policy="declared_field"` |
| `client_unverified` | 5 | declared column isn't in the published schema; verified against actual rows at runtime |
| `unsupported` | 8 | no knowledge axis at all; **refused** |

When the API supplies a `knowledge_date` column, it wins over the declared field — and if those dates are imputed, you hear about it:

```python
import warnings
# ImputedKnowledgeDateWarning:
#   1,234 of 1,242 rows (99.4%) carry kd_imputed=true (kd_source=statutory_deadline):
#   the knowledge date was derived from a statutory filing deadline, not observed
#   from an announcement. Treat this as a rule-based approximation of what was
#   knowable, not as an observed disclosure timestamp.
```

An imputed knowledge date is a rule, not a fact, and this SDK will never present it as one.

### 3. Gaps and truncation surfaced, never filled

No zero-filling. No forward-filling. No interpolation. Missing data is reported as missing, labelled with where the knowledge came from:

```python
df = c.twse_daily_price(ticker="2330", start="2024-01-01")
m = df.twmd                       # or c.last_meta

m.truncated       # True if the row limit was hit on a route that can't paginate
m.data_gaps       # [Gap(2024-02-08..2024-02-14, no_row_for_trading_day), ...]
m.gaps_source     # 'server' | 'client_derived' | 'unsupported' | 'unknown'
m.coverage_min, m.coverage_max
m.source_role, m.lineage, m.data_as_of
```

`gaps_source` matters. Only 22 of 82 routes report gaps themselves; for daily per-entity datasets the SDK can derive them against `trading_calendar` (`derive_gaps=True`, costs one extra request), and where it can't do either it says `unknown` rather than implying there are none.

Truncation is flagged because only 9 of 82 routes support `offset`. On those 9 the SDK paginates to completion; on the other 73, hitting the limit sets `truncated=True` and warns. A short result is never silently passed off as a complete one.

---

## Command line

Installing the package also installs `twmd`:

```bash
pip install twmarketdata

twmd datasets --free-only            # what answers with no key
twmd describe monthly_revenue        # grain, filters, and its as_of semantics
twmd coverage twse_daily_price       # the window we actually cover
twmd get monthly_revenue --ticker 2330 --as-of 2024-06-30 --format csv
twmd auth status                     # which key is in use (never echoes it)
```

It is a thin shell over the same `Client` and registry this README documents — not a second
implementation. A CLI that built its own requests would carry a second copy of the point-in-time
rules, and two copies drift.

Three things it does on purpose:

1. **Omitting `--as-of` prints a warning to stderr.** You get the latest revision, including values
   revised after the date you may be reasoning about. For a backtest that is a look-ahead leak, and
   the response looks completely normal without the warning.
2. **Gaps and truncation go to stderr; data goes to stdout.** So `twmd get … --format csv > out.csv`
   gives you a clean CSV *and* you still see what was missing. (Python de-duplicates repeated
   warnings by default; the CLI turns that off, because every gap is worth seeing.)
3. **Exit codes are classified**: `3` auth, `4` entitlement, `5` unknown dataset, `6` rate limited,
   `7` invalid parameter, `8` upstream. Returning `1` for everything forces you to grep error
   strings, and error strings change.

`twmd` does not pull in pandas — it uses the SDK's no-pandas path, so the install stays small.

---

## Agents: the MCP server

If you are wiring an agent rather than writing Python, the same data is served over MCP at
`https://mcp.twmarketdata.com/mcp` — 34 tools, plus reference resources that read with **no key at
all**. See [TW-Market-Data/tw-market-data-mcp](https://github.com/TW-Market-Data/tw-market-data-mcp).

---

## FinMind compatibility

Existing FinMind-shaped code can run against TW Market Data with the call sites unchanged:

```python
from twmd.compat import finmind as fm

df = fm.taiwan_stock_daily(stock_id="2330", start_date="2026-08-01")
```

Every recognised call is graded, and the grade decides what happens:

| grade | meaning | behaviour |
|---|---|---|
| **A** (19) | same grain and meaning | returns data |
| **B** (17) | same fact, different shape | reshapes, or refuses and points at the native method |
| **C** (24) | TWMD covers it differently | returns data + `CompatSubstitutionWarning` explaining the difference |
| **D** (46) | no equivalent in the 82 datasets | raises `NotMappedError` |

```python
fm.taiwan_stock_trading_daily_report(stock_id="2330")
# NotMappedError: taiwan_stock_trading_daily_report has no TW Market Data
# equivalent: Broker-branch daily flow is not in the 82. TWMD has the branch
# ROSTER (broker_branch_reference / securities_firm_master) but not
# branch-level buy/sell.
```

D-grade calls raise instead of returning an empty frame, because an empty frame reads as "your query matched nothing" — a different claim from "this data doesn't exist here". Nine further mappings are candidates that haven't been verified row by row yet; they also raise, and name the candidate dataset, rather than shipping possibly-wrong.

**Two honest limits.** Parameter names are mirrored, but **response column names are TWMD's** — a `stock_id` alias is added where an identifier column exists. Mirroring column names would mean comparing live responses from both services, which this project does not do. And the mapping table was built by reading the public method signatures of the open-source package (FinMind v2.0.7, read 2026-08-12) — the FinMind service was never called and no credentials were used.

`mapping/finmind_map.csv` records all 144 rows with their grade, confidence, and verification source.

> This project is **not affiliated with, endorsed by, or sponsored by FinMind**. The name is used nominatively to identify the interface being made compatible. No FinMind source code is included or redistributed. See [NOTICE](NOTICE).

---

## Free tier

No API key required for **five demo symbols**: `2330` 台積電, `2317` 鴻海, `2454` 聯發科, `0050` 元大台灣50, `2603` 長榮.

Every example in this README runs against one of the **16 datasets measured to return data without a key**:

`security_master` · `trading_calendar` · `monthly_revenue` · `twse_daily_price` · `index_constituents` · `trading_rules_reference` · `bond_convertible_reference` · `broker_branch_reference` · `warrants_reference` · `company_industry_exposures` · `company_peer_groups` · `securities_firm_master` · `fund_etf_metadata` · `issuer_classification` · `stock_delisting_lifecycle` · `stock_split_par_value_events`

```python
twmd.runnable_without_key()     # the list above, measured not declared
twmd.free_tier_symbols()        # the five demo symbols
```

That list is *measured*, not read off the tier column: three datasets marked `tier=free` return 401 in practice, so they're excluded. Requesting any other symbol without a key raises `FreeTierSymbolError` listing the five, rather than returning an empty frame.

With a key, everything your plan includes is available:

```python
c = Client("your_api_key")            # or set TWMD_API_KEY
```

The key is read from the argument first, then `TWMD_API_KEY`. It is never logged and never appears in `repr()`.

---

## Errors

```
TwmdError
├── TwmdConfigError → FreeTierSymbolError
├── TwmdAuthError   → MissingApiKeyError, InvalidApiKeyError,
│                     TierRequiredError, InsufficientCreditsError
├── TwmdRequestError → DatasetNotFoundError, UnsupportedParameterError
├── RateLimitedError        429, and 403 temporarily_blocked
├── EndpointRetiredError    410
├── TwmdServerError         5xx and transport failures
├── PointInTimeUnavailable  as_of can't be honoured for this dataset
└── NotMappedError          compat call with no TWMD equivalent
```

Two of these are worth calling out:

**`403 temporarily_blocked` is a rate limit, not a permissions problem.** It reads like "forbidden" and sends people hunting for a plan bug that isn't there. The SDK classifies it as a rate limit, retries with exponential backoff and jitter, and says so in the message. Default `max_concurrency` is **2** — during measurement, four concurrent requests tripped a block that persisted for tens of minutes.

**`UnsupportedParameterError` is deliberate.** Passing `start=` to a dataset with no date parameter is an error, not something to quietly drop — silently ignoring it returns a full unfiltered history that looks like a filtered one.

---

## Response type

`TwmdFrame` subclasses `pandas.DataFrame`, so `isinstance` checks pass and the whole pandas ecosystem works. Metadata rides along as `df.twmd`.

pandas preserves `_metadata` through slicing and copying, but some operations (`merge`, several groupby paths) build a fresh frame and drop it. So the same `Meta` is always on the client as `c.last_meta`, which no pandas operation can lose.

Without pandas the SDK still works and returns `list[dict]`. Pass `raw=True` for the decoded JSON envelope.

---

## Coverage and limits

- **82 sellable datasets.** The registry lists 125 entries and the OpenAPI spec mounts 119 dataset routes; 82 is the sellable, queryable subset this SDK ships.
- **Dataset status is visible.** 75 are `active`; 5 `partial`, 1 `planned`, 1 `private_beta` warn on use, because a partial series shouldn't be mistaken for a complete one.
- **Registry is generated and dated.** `twmd.REGISTRY_MEASURED_ON` tells you when the routes and semantics were last verified against the live API.

---

## Upgrading from 0.1.0

0.2.0 keeps the same distribution (`twmarketdata`) and the same import name
(`twmd`), so `pip install -U twmarketdata` is the whole upgrade. Everything
0.1.0 exported still resolves and still works, now emitting `DeprecationWarning`
with the replacement named:

| 0.1.0 | 0.2.0 |
|---|---|
| `client.get_dataset("twse-daily-price", symbol="2330")` | `client.twse_daily_price(ticker="2330")` |
| `client.get_all(...)` / `iter_pages(...)` | `client.dataset(...)` — paginates internally |
| `client.list_datasets()` | `twmd.datasets()` / `twmd.capabilities(name)` |
| `twmd.access.is_key_free(...)` | `twmd.runnable_without_key()` |
| `twmd.frames.to_dataframe(payload)` | returned frames already carry `.twmd` metadata |
| `TwmdAPIError`, `TwmdPaymentRequired`, … | still importable; `TwmdPaymentRequired` keeps `payment` / `price` / `credits_url` / `purchase_hint` |

Two behaviours changed on purpose, both toward accuracy:

- **The access tables were re-measured.** 0.1.0 recorded 2 key-free datasets
  from a probe on 2026-07-21. A full 82-route sweep, plus a second sweep with a
  non-demo ticker to separate "open to anyone" from "demo symbols only", found
  15 open and the same 3 sample-only. Names, semantics and return types are
  unchanged.
- **Pagination stops when the server ignores `offset`.** Measured on
  `index-constituents`: offsets 0, 3 and 6 returned identical pages. Continuing
  would append duplicate rows and present them as a full history, so pagination
  halts and the result is flagged `truncated`.

0.1.0 remains MIT; 0.2.0 onward is Apache-2.0.

---

## Development

```bash
pip install -e ".[dev]"
pytest                        # offline suite
pytest -m network             # live free-tier checks, no key needed
```

Regenerating the registry after an API change:

```bash
python tools/build_mapping.py    # re-derive the mapping tables from live sources
python tools/gen_registry.py     # → twmd/_registry.json
python tools/gen_methods.py      # → twmd/_methods.py + .pyi
python tools/gen_compat_map.py   # → twmd/compat/_finmind_map.json
```

Design notes and the full evidence trail live in [`DESIGN_v1.md`](DESIGN_v1.md), [`mapping/`](mapping/), and [`mapping/sources/`](mapping/sources/).

---

## Links

- Website: <https://twmarketdata.com>
- Pricing: <https://twmarketdata.com/en/pricing>
- REST API (OpenAPI): <https://api.twmarketdata.com/openapi.json>
- MCP server: <https://mcp.twmarketdata.com/mcp> ·
  [docs & issues](https://github.com/TW-Market-Data/tw-market-data-mcp)
- This repo: <https://github.com/TW-Market-Data/twmarketdata>

---

## License

[Apache-2.0](LICENSE). See [NOTICE](NOTICE) for trademark and compatibility statements.

*Not investment advice.*
