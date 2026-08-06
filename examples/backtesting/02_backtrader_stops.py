"""MA-crossover with take-profit / stop-loss on 2330, event-driven.

Engine: Backtrader. Data: twmarketdata. Use this (not the vectorized example)
whenever the logic is path-dependent — stops, take-profit, position sizing —
because those are wrong to model vectorized.

    pip install twmarketdata backtrader

2330 is a key-free sample ticker; any other ticker needs a free-tier key
(set TWMD_API_KEY). Backtrader fills a market order at the NEXT bar's open, so
there is no look-ahead.

NOTE: not run end-to-end in this repo's CI (the sandbox cannot reach the live
API). Run it once and confirm the numbers before relying on it.
"""

import backtrader as bt
import pandas as pd

from twmd import Client

FAST, SLOW = 5, 20
TAKE_PROFIT = 0.15
STOP_LOSS = 0.08
FEE = 0.001425          # brokerage, per side
TAX_ON_SELL = 0.003     # transaction tax, sells only
INIT_CASH = 1_000_000


class TwCommission(bt.CommInfoBase):
    """Taiwan cost model: brokerage both sides, transaction tax on sells only."""

    params = (("commission", FEE), ("tax", TAX_ON_SELL),
              ("stocklike", True), ("commtype", bt.CommInfoBase.COMM_PERC))

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        comm = value * self.p.commission
        if size < 0:                       # a sell also pays the tax
            comm += value * self.p.tax
        return comm


class MaCrossStops(bt.Strategy):
    params = dict(fast=FAST, slow=SLOW, tp=TAKE_PROFIT, sl=STOP_LOSS)

    def __init__(self):
        fast = bt.ind.SMA(period=self.p.fast)
        slow = bt.ind.SMA(period=self.p.slow)
        self.cross = bt.ind.CrossOver(fast, slow)
        self.entry_price = None

    def next(self):
        if not self.position:
            if self.cross > 0:
                self.buy()
                self.entry_price = self.data.close[0]
        else:
            ret = self.data.close[0] / self.entry_price - 1
            if ret >= self.p.tp or ret <= -self.p.sl or self.cross < 0:
                self.close()


df = Client().get_dataset("twse-daily-price", symbol="2330", limit=5000).sort_values("date")
for col in ["open", "high", "low", "close", "volume_shares"]:
    df[col] = df[col].astype(float)          # the API returns numbers as strings
df["datetime"] = pd.to_datetime(df["date"])
df = df.set_index("datetime")
print("rows:", len(df), "| data_as_of:", df.attrs.get("data_as_of"))

feed = bt.feeds.PandasData(dataname=df, open="open", high="high", low="low",
                           close="close", volume="volume_shares", openinterest=None)

cerebro = bt.Cerebro()
cerebro.adddata(feed)
cerebro.addstrategy(MaCrossStops)
cerebro.broker.setcash(INIT_CASH)
cerebro.broker.addcommissioninfo(TwCommission())
cerebro.addsizer(bt.sizers.PercentSizer, percents=95)   # leave headroom for commission — an all-in order gets rejected for insufficient cash once the fee is added
cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", timeframe=bt.TimeFrame.Days)
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

start = cerebro.broker.getvalue()
strat = cerebro.run()[0]
end = cerebro.broker.getvalue()

trades = strat.analyzers.trades.get_analysis()
won = trades.get("won", {}).get("total", 0)
total = trades.get("total", {}).get("closed", 0)
print("total return:  %6.1f%%" % ((end / start - 1) * 100))
print("max drawdown:  %6.1f%%" % strat.analyzers.dd.get_analysis().max.drawdown)
print("sharpe:        %6s" % strat.analyzers.sharpe.get_analysis().get("sharperatio"))
print("trades:        %6d" % total)
print("win rate:      %6.1f%%" % (100 * won / total if total else 0))
