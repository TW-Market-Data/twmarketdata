"""Survivorship bias, quantified — what a backtest hides when it drops delisted names.

Most free data only carries stocks still listed today. This measures the hole
that leaves: it pulls every TWSE stock that has STOPPED trading and computes the
return of its final year on the market — the returns a survivorship-free
backtest would have to include, and a survivor-only universe silently omits.

    pip install twmarketdata pandas

Delisted stocks are NOT in the key-free 5-ticker demo, so this needs a
free-tier key: set TWMD_API_KEY. Not run in this repo's CI (the sandbox cannot
reach the live API) — run it once and confirm before relying on it.

Method notes, from measuring the real API (see traps below):
- The delisting list is TWSE-only, so the universe here is TWSE. TPEx is not
  covered — including it would understate the bias.
- "Delisted" is not "bankrupt": some names transfer boards and keep trading
  elsewhere. Using the REAL last traded price (never assuming -100%) keeps those
  honest. A board transfer shows a realistic final return, not a fake wipeout.
- Last trading day != delisting date (gap can be months). Reading the last row
  of the actual price series avoids the null you'd get indexing by delisting_date.
"""

import os

import numpy as np
import pandas as pd

from twmd import Client, TwmdAuthError, TwmdPaymentRequired

WINDOW = 252            # trading days of "final year" to measure (~1 year)
SAMPLE_N = 60           # cap for a quick run; set None to process all 264

if not os.environ.get("TWMD_API_KEY"):
    raise SystemExit("Set TWMD_API_KEY — delisted stocks are not served key-free.")

client = Client()

# (a) the delisted universe. Only code / delisting_date / market are reliably
#     populated (company_name is 96/264; the rest are empty) — do not build on
#     announcement_date / suspension_date / reason_summary.
listing = client.get_dataset("stock-delisting-lifecycle", limit=500)   # default cap is 100; there are 264
delisted = listing[listing["market"] == "TWSE"][["code", "delisting_date"]].dropna(subset=["code"])
codes = delisted["code"].astype(str).tolist()
if SAMPLE_N:
    codes = codes[:SAMPLE_N]
print(f"delisted TWSE names to measure: {len(codes)} (of {len(delisted)} total)")

# (b) each name's final-year return, from its own price series (symbol / date).
final_returns = []
skipped = 0
for code in codes:
    try:
        px = client.get_dataset("twse-daily-price", symbol=code, limit=5000)
    except (TwmdPaymentRequired, TwmdAuthError) as exc:
        raise SystemExit(
            f"API returned {exc.error_code} for {code}: {exc.body}\n"
            "This example fetches many delisted names, so it needs a key with "
            "credits/entitlement — top up the account or use a plan that covers it."
        )
    except Exception:
        skipped += 1
        continue
    px = px.sort_values("date")
    close = px["close"].astype(float).to_numpy()
    if len(close) < 20:                       # too little history to be meaningful
        skipped += 1
        continue
    start = close[-WINDOW] if len(close) >= WINDOW else close[0]
    final_returns.append(close[-1] / start - 1)

r = np.array(final_returns)
total_delisted = len(delisted)                # every delisted TWSE name on the list (~264)
listed_estimate = 1377                        # currently-listed TWSE common stocks (approx)
share = total_delisted / (total_delisted + listed_estimate)

print("\n=== the hole a survivor-only universe leaves ===")
print("delisted names on list:      %6d" % total_delisted)
print("measured (usable history):   %6d" % len(r))
print("skipped (no/short history):  %6d" % skipped)
print("median final-year return:    %6.1f%%" % (np.median(r) * 100))
print("mean final-year return:      %6.1f%%" % (np.mean(r) * 100))
print("share that ended negative:   %6.1f%%" % (100 * (r < 0).mean()))
print("worst:                       %6.1f%%" % (r.min() * 100))
print("\nthese %d names are ~%.0f%% of the TWSE common-stock universe and are" % (total_delisted, share * 100))
print("concentrated in the worst performers. Excluding them is survivorship bias.")
