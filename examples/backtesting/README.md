# Backtesting with twmarketdata

Professional backtesting is not a strategy box on a website — it is your own
Python, run against data you trust. This folder shows how to point an
open-source backtest engine at Taiwan market data pulled with `twmarketdata`.

```bash
pip install twmarketdata vectorbt        # vectorized, fast
pip install twmarketdata backtrader      # event-driven, realistic fills
```

> Key-free access returns only a short recent window (~120 rows for the five
> sample tickers). Set `TWMD_API_KEY` — even a free-tier key — for full history.

## Why backtest on this data

**Survivorship bias is the quiet killer of retail backtests.** Most free data
sources only carry stocks that are *still listed today*. Backtest a universe
built from those and you have silently excluded every company that went to
zero, got delisted, or was acquired — so your returns look far better than any
strategy could ever have achieved in real time.

`twse-daily-price` keeps the full price history of stocks that have **stopped
trading**, with official delisting dates where available. That is exactly the
data a backtest needs to be honest. `03_survivorship_bias_demo` measures the
gap directly: the same strategy, same period, run once *with* delisted names
and once *without* — the difference is the bias.

Every response also carries `data_as_of` and `lineage`, so a backtest can
record precisely which data it ran on.

## What's here

| Notebook | Engine | Shows |
| --- | --- | --- |
| `01_vectorbt_ma_crossover` | VectorBT | Vectorized MA-crossover on 2330, Taiwan cost model, benchmark vs buy-and-hold |
| `02_backtrader_stops` | Backtrader | Event-driven strategy with take-profit / stop-loss and next-bar fills |
| `03_survivorship_bias_demo` | VectorBT | With vs without delisted names — the bias, quantified |

## Which engine when

- **VectorBT** — vectorized over pandas/NumPy. Fast enough to sweep parameters
  or a whole universe. Best for research, screening, and the survivorship demo.
- **Backtrader** — event-driven, bar by bar. Use it when the logic is
  path-dependent — stops, take-profit, position sizing, next-bar execution —
  because those are wrong to model vectorized.

## Taiwan cost model (used in every example)

Real fills, not frictionless. The examples charge:

- **Brokerage fee** 0.1425% per side (before any broker discount)
- **Transaction tax** 0.3% on sells (0.1% for day trades and ETFs)
- **Slippage** a configurable few basis points

A backtest that ignores these overstates every result. They are parameters at
the top of each notebook — set your own broker's rate.

## Avoiding look-ahead bias

The one rule that separates a real backtest from a misleading one: **never let
a bar's own close (or anything from the future) drive a trade in that same
bar.** The examples decide on bar *t* and execute at the open of bar *t+1*.
Indicators use only data available up to the decision point.

## Not investment advice

These are engineering examples for research and education. A backtest is a
simulation of the past; it is not a prediction, a recommendation, or a signal,
and past performance does not indicate future results. Verify data against the
original sources before relying on it. Use of the underlying API is governed by
TW Market Data's terms.
