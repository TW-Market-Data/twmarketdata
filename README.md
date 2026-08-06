# twmd — Taiwan stock market data for Python

[![PyPI](https://img.shields.io/pypi/v/twmarketdata)](https://pypi.org/project/twmarketdata/)
[![Python](https://img.shields.io/pypi/pyversions/twmarketdata)](https://pypi.org/project/twmarketdata/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/twmarketdata)](https://pypi.org/project/twmarketdata/)

**English** · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md)

Official Python client for the **[TW Market Data](https://twmarketdata.com)** API —
TWSE / TPEx prices, financial statements, institutional flows, valuation and factor
data, and 80+ datasets, returned as pandas DataFrames. **Five sample tickers work
with no API key**, so you can try it in one line.

```bash
pip install twmarketdata
```
```python
from twmd import Client
Client().get_dataset("twse-daily-price", symbol="2330", limit=5)   # no key needed
```

**Get started:** [Free API key](https://twmarketdata.com) · [Pricing](https://twmarketdata.com/pricing) · [Docs](https://twmarketdata.com/docs) · [Dataset catalog](https://twmarketdata.com/datasets) · [MCP / AI agents](https://twmarketdata.com/docs/tools-and-mcp)

---

`twmd` retrieves published datasets over HTTP and returns them as pandas
DataFrames. It is a transport layer for data retrieval, intended for research
and educational use. It fetches records as the API publishes them and performs
no analysis, scoring, ranking, or interpretation of any kind. Deciding what the
data means, and what if anything to do about it, is entirely the caller's own
work and responsibility.

Responses carry the API's own `lineage.not_investment_advice` flag; this client
preserves it unmodified.

## Install

```bash
pip install twmarketdata
```

The distribution is named `twmarketdata`; the import package is `twmd`:

```python
import twmd
```

Pure Python. Dependencies are `httpx` and `pandas` — no compiled extensions, no
system libraries, installable in a restricted sandbox.

Requires Python 3.9 or newer. The floors are deliberately low (`pandas>=1.5`,
`httpx>=0.27`) so this installs into existing environments without forcing an
upgrade, and CI runs the full suite pinned to exactly those floors so they stay
honest rather than aspirational.

One caveat that is not ours to fix: pandas 1.5 wheels are built against the
numpy 1.x C ABI and fail at import under numpy 2 with `numpy.dtype size
changed`. If you are pinned to pandas 1.x, pin `numpy<2` alongside it. Anything
from pandas 2.2.2 onward works with numpy 2 unconstrained.

## Quick start — no API key needed

Five sample tickers are served without credentials on selected datasets, so
this runs with zero configuration:

```python
from twmd import Client

client = Client()
df = client.get_dataset("twse-daily-price", symbol="2330", limit=5)

print(df[["date", "open", "high", "low", "close", "volume_shares"]])
print(df.attrs["data_as_of"])       # data freshness date
print(df.attrs["lineage"])          # provider, source endpoints, source table
```

## Why twmd

- **Official sources, stated plainly.** Every response carries its `lineage` —
  provider, official source endpoint, and source table — plus a `data_as_of`
  freshness date. Nothing is fabricated, interpolated, or back-filled.
- **Retrieval only, no hidden opinions.** This client fetches data and returns it;
  it produces no scores, signals, or recommendations. What the data means is yours
  to decide.
- **Honest coverage.** Datasets report what they actually have. Gaps are shown as
  gaps — never filled with zeros or another ticker's rows.
- **Pure Python.** `httpx` + `pandas`, no compiled extensions — installs anywhere,
  even a restricted sandbox. CI proves it across Linux / macOS / Windows on
  Python 3.9–3.13.
- **Built for AI agents too.** The same data is reachable over
  [MCP](https://twmarketdata.com/docs/tools-and-mcp) and an
  [`llms.txt`](https://twmarketdata.com/llms.txt) index, so agents can discover and
  query datasets directly.

## Authentication

Set your key in the environment; it is never written to disk or logged:

```bash
export TWMD_API_KEY="sk_live_..."
```

`Client()` picks it up automatically. You may also pass `Client(api_key=...)`
explicitly. With no key set, the client runs in key-free mode and reaches the
datasets listed below.

## Key-free access matrix

Key-free access is scoped **per dataset**, not globally per ticker. The same
ticker that is served on one dataset may require a key on another. Measured
against the live API on 2026-07-21:

| Tier | Datasets | Tickers served without a key |
| --- | --- | --- |
| Open | `security-master`, `market-index` | any |
| Sample | `twse-daily-price`, `tpex-daily-price`, `monthly-revenue` | `2330`, `2317`, `2454`, `0050`, `2603` only |
| Key required | everything else, including `institutional-flow`, `market-prices`, `financial-metrics`, `income-statement`, `balance-sheet` | none |

Check before requesting:

```python
from twmd import is_key_free

is_key_free("twse-daily-price", "2330")     # True
is_key_free("twse-daily-price", "1101")     # False — outside the sample set
is_key_free("security-master", "1101")      # True — open dataset
is_key_free("institutional-flow", "2330")   # False — key required
```

Datasets not in the table are treated as key-required, which is the safe
default. The client never blocks a request on this basis — it only uses the
matrix to explain a 401 after the fact.

## DataFrames and metadata

Records become rows. Everything else in the response envelope is preserved on
`df.attrs`.

The API uses **two envelope shapes**, and `twmd` handles both transparently:

```python
# rows / count — twse-daily-price, tpex-daily-price, monthly-revenue
df.attrs["dataset"]       # "twse_daily_price"
df.attrs["count"]         # record count
df.attrs["data_as_of"]    # data freshness date
df.attrs["source_role"]   # e.g. "official_twse"
df.attrs["lineage"]       # provider, official_source, source_endpoints, table
df.attrs["meta"]          # last_trading_day, market_status

# items / row_count — security-master, market-index
df.attrs["dataset_id"]                  # "security-master"
df.attrs["row_count"]                   # record count
df.attrs["as_of_date"]                  # snapshot date
df.attrs["survivorship_bias_warning"]   # integrity caveat raised by the API
```

Envelope contents vary by dataset — `monthly-revenue` sends only `dataset`,
`rows` and `count` — so read `attrs` defensively.

Records in the `items` variant contain nested objects (`security_identity`,
`market_identity`, `index_level`). These stay as dict-valued columns rather than
being flattened, so a DataFrame reflects what the API actually sent. Expand one
when you want to:

```python
import pandas as pd
identity = pd.json_normalize(df["security_identity"])
```

Note that `security-master` carries a `survivorship_bias_warning` stating the
current master is not point-in-time complete. It is surfaced on `attrs`
unmodified; check it before using that dataset for historical work.

## Errors

```python
from twmd import Client, TwmdAuthError, TwmdPaymentRequired

try:
    df = client.get_dataset("institutional-flow", symbol="2330")
except TwmdAuthError as exc:
    print(exc.error_code)   # "missing_api_key" or "invalid_api_key"
    print(exc.body)         # decoded response body, verbatim
```

Every `TwmdAPIError` subclass — every row in the table below except the last —
exposes `.status_code`, `.body` (decoded body, unmodified), `.text` and
`.error_code`. `TwmdTransportError` and `TwmdConfigError` derive from `TwmdError`
directly and carry none of those, since no response was received.

| Status | Exception | Retried |
| --- | --- | --- |
| 401 | `TwmdAuthError` | no |
| 402 | `TwmdPaymentRequired` | no |
| 404 | `TwmdNotFoundError` | no |
| 422 | `TwmdValidationError` | no |
| 429 | `TwmdRateLimitError` | yes |
| 5xx | `TwmdServerError` | yes |
| network failure | `TwmdTransportError` | yes |

Retries use exponential backoff with jitter. A `Retry-After` header — in either
RFC 7231 form, delta-seconds or HTTP-date — overrides that and is honoured
exactly, with no jitter and no shortening, since retrying sooner than the server
permitted is worse than waiting too long. If it asks for more than
`RETRY_AFTER_MAX` (120s) the client stops and raises the server's error rather
than blocking for minutes.

401 messages are annotated with the key-free status of the dataset and ticker
you asked for, so "I forgot my key" is distinguishable from "that ticker is not
in the sample set".

### 401 vs 402

These mean different things and have different answers:

- **401** — no key, or a bad key. Answered by registering / adding a key.
- **402** — a valid key whose **plan does not include** the dataset. Answered by
  upgrading the plan.

The live 402 body (verified 2026-07-21):

```json
{
  "error": "not_entitled_for_dataset",
  "message": "您的方案未包含此資料集…",
  "payment": {
    "price": "pro",
    "credits_url": "https://twmarketdata.com/pricing",
    "purchase_hint": "upgrade_plan"
  }
}
```

The whole body is preserved verbatim on `.body`. For convenience, the `payment`
object and its fields are also exposed on the exception — read from whatever the
API sent, never fabricated:

```python
except TwmdPaymentRequired as exc:
    exc.payment        # the payment object, or None
    exc.price          # "pro"
    exc.credits_url    # "https://twmarketdata.com/pricing"
    exc.purchase_hint  # "upgrade_plan"
    exc.body           # the full response, unmodified
```

## Source attribution

Pass `source` to mark every request with the integration that produced it, so
the publisher can attribute traffic:

```python
client = Client(source="ecosys/tradingagents")
```

It is attached as a `source` query parameter on every request. A per-call
`source=` on `get_dataset` overrides the client-wide value. It is an ordinary
query parameter — it does not change the response, does not enter a data
response's `request_context.filters`, and carries nothing about the user. Leave
it unset to send nothing.

## Pagination

```python
df = client.get_all("twse-daily-price", symbol="2330", limit=1000)

for page in client.iter_pages("twse-daily-price", symbol="2330", limit=500):
    process(page)
```

The API publishes no cursor: no `cursor` or `next_cursor` field appears in any
response or in the OpenAPI document. Paging is `limit`/`offset`, and `offset`
was measured to be **ignored** on the key-free endpoints — `offset=3` returned
the same records as `offset=0`.

So pagination here is defensive. It advances `offset` as documented, then stops
when either a page comes back shorter than `limit`, or a page repeats the
previous page's first record — the signature of a silently ignored `offset`.
Against endpoints that ignore `offset` this yields exactly one page, which is
the correct outcome rather than a failure. `max_pages` caps the loop.

## `as_of`

`get_dataset()` accepts an `as_of` argument and forwards it as a query
parameter. **Its scope is narrow.** As measured on 2026-07-21:

- `as_of` is declared on exactly four endpoints — `income-statement`,
  `cash-flow-statement`, `balance-sheet`, `financials` — all of which require an
  API key.
- On every other endpoint it is not a declared parameter. The API silently
  ignores unknown query parameters, returning 200 rather than 422, so passing
  `as_of` there has no observable effect and raises no error.
- Its behaviour on the four declared endpoints is **unverified** by this
  project, which has no credentials to exercise them.

Treat `as_of` as forwarded-but-unconfirmed rather than as a general
point-in-time facility. The `data_as_of` field in responses is a data-freshness
date and is a different thing.

## Development

```bash
pip install -e ".[test]"
pytest -m "not live"    # offline, no network
pytest -m live          # hits the real API, key-free paths only
```

The live suite asserts a sample of the key-free matrix — seven dataset/ticker
pairs — still matches what the API serves, so drift in those surfaces as a test
failure. It is a tripwire, not full coverage: the five sample tickers are
verified only against `twse-daily-price`, and three datasets listed as
key-required are assumed rather than probed (see
`access.PRESUMED_KEY_REQUIRED_DATASETS`, and `access.provenance()` to tell the
two apart).

## Scope

This package retrieves data. It does not generate recommendations, forecasts,
signals, valuations, or opinions about any security, and nothing it returns
should be read as such. The data is provided for research and educational
purposes; verify it against the original sources before relying on it. Use of
the underlying API is governed by TW Market Data's own terms.

## License

MIT
