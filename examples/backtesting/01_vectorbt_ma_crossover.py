"""Moving-average crossover backtest on 2330, with the Taiwan cost model.

Engine: VectorBT (vectorized). Data: twmarketdata.
2330 is one of the five key-free sample tickers, so this example runs with no
API key. For any other ticker you need a free-tier key: set TWMD_API_KEY.

    pip install twmarketdata vectorbt

NOTE: not yet run end-to-end in this repo's CI (the sandbox cannot reach the
live API). Run it once and confirm the numbers before relying on it.
"""

import numpy as np
import vectorbt as vbt

from twmd import Client

# --- Taiwan cost model (edit to your broker's terms) -----------------------
FEE = 0.001425          # brokerage, per side, before any discount
TAX_ON_SELL = 0.003     # transaction tax, sells only (0.001 for day trades/ETFs)
SLIPPAGE = 0.0005       # a few basis points
INIT_CASH = 1_000_000
FAST, SLOW = 5, 20      # MA windows — the tunable parameters FinMind hides

# --- Pull the data ---------------------------------------------------------
# One call returns up to the endpoint's row cap; raise `limit` for more history.
df = Client().get_dataset("twse-daily-price", symbol="2330", limit=5000)
df = df.sort_values("date").reset_index(drop=True)
print("rows:", len(df), "| through:", df["date"].iloc[-1], "| data_as_of:", df.attrs.get("data_as_of"))

close = df["close"].astype(float).to_numpy()
dates = df["date"].to_numpy()

# --- Strategy: fast MA crosses slow MA -------------------------------------
fast_ma = vbt.MA.run(close, FAST)
slow_ma = vbt.MA.run(close, SLOW)
entries = fast_ma.ma_crossed_above(slow_ma)
exits = fast_ma.ma_crossed_below(slow_ma)

# vectorbt's `fees` is charged on both sides; the sell-only tax is folded in as
# half its rate across the round trip so the total drag is right. This is an
# approximation — an event-driven engine (see 02_backtrader_stops) models the
# sell tax exactly. Signals fire on bar t and fill on t+1 (no look-ahead).
pf = vbt.Portfolio.from_signals(
    close,
    entries,
    exits,
    fees=FEE + TAX_ON_SELL / 2,
    slippage=SLIPPAGE,
    init_cash=INIT_CASH,
    freq="1D",
)

# --- Benchmark: buy and hold the same stock, same costs --------------------
bench = vbt.Portfolio.from_holding(close, init_cash=INIT_CASH, fees=FEE, slippage=SLIPPAGE, freq="1D")

print("\n=== strategy ===")
print(pf.stats())
print("\nstrategy total return:  %6.1f%%" % (pf.total_return() * 100))
print("buy & hold total return:%6.1f%%" % (bench.total_return() * 100))
print("excess vs buy & hold:   %6.1f%%" % ((pf.total_return() - bench.total_return()) * 100))
print("max drawdown:           %6.1f%%" % (pf.max_drawdown() * 100))
print("sharpe:                 %6.2f" % pf.sharpe_ratio())
print("trades:                 %6d" % pf.trades.count())
print("win rate:               %6.1f%%" % (pf.trades.win_rate() * 100))
