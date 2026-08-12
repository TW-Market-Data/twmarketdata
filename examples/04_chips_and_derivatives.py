"""Chip flows and derivatives context.  ⚠ RECORDED PENDING TEST KEY

    TWMD_API_KEY=<your key> python examples/04_chips_and_derivatives.py

Requires a key. Tiers used here: institutional_flow and margin_short are
starter, foreign_holding and margin_system_stats are pro, taifex_put_call_ratio
and taifex_atm_iv are max.

STATUS: written but NOT yet executed against the live API. Output in the
comments is what the SDK is built to produce, not a transcript, and will be
replaced with real output once a restricted test key is issued.

Two honesty features worth watching in the metadata here:

* ``margin_system_stats.maintenance_ratio`` is documented NULL upstream -- not
  loaded. The SDK surfaces the column as NA and records it rather than
  substituting a computed proxy.
* ``taifex_atm_iv`` is a DERIVED implied volatility (Black-Scholes from official
  TXO prices plus TAIEX spot). It is not the official VIX, and neither the SDK
  nor the compat layer will call it one.
"""
import twmd
from twmd import Client
from twmd.errors import MissingApiKeyError, TierRequiredError

TICKER = "2330"
c = Client()

print("=" * 74)
print("What each dataset supports, before spending a request")
print("=" * 74)
for key in ("institutional_flow", "margin_short", "foreign_holding",
            "margin_system_stats", "taifex_put_call_ratio", "taifex_atm_iv"):
    caps = twmd.capabilities(key)
    print("%-24s tier=%-10s as_of=%-10s gaps=%s"
          % (key, caps["tier"], caps["as_of"], caps["data_gaps"]))

try:
    print()
    print("=" * 74)
    print("Chip flows for %s" % TICKER)
    print("=" * 74)
    flow = c.institutional_flow(ticker=TICKER, start="2026-07-01")
    print("institutional_flow rows: %d" % len(flow))
    print("  GRAIN NOTE: TWMD serves the three-institution NET TOTAL. A per-type")
    print("  breakdown (foreign / trust / dealer) is not among the 82, which is")
    print("  why twmd.compat.finmind grades that mapping C and warns.")

    margin = c.margin_short(ticker=TICKER, start="2026-07-01")
    print("\nmargin_short rows: %d" % len(margin))

    stats = c.margin_system_stats(start="2026-07-01")
    print("\nmargin_system_stats rows: %d" % len(stats))
    if len(stats) and "maintenance_ratio" in getattr(stats, "columns", []):
        nulls = int(stats["maintenance_ratio"].isna().sum())
        print("  maintenance_ratio nulls: %d/%d — documented upstream as not loaded."
              % (nulls, len(stats)))
        print("  The SDK leaves it NA. It does not compute a stand-in.")

    print()
    print("=" * 74)
    print("Derivatives context (tier=max)")
    print("=" * 74)
    pcr = c.taifex_put_call_ratio(start="2026-07-01")
    print("taifex_put_call_ratio rows: %d" % len(pcr))

    iv = c.taifex_atm_iv(start="2026-07-01")
    print("taifex_atm_iv rows: %d" % len(iv))
    print("  ⚠ DERIVED, not the official VIX: Black-Scholes inversion from")
    print("    official TXO option prices + TAIEX spot. Label it as derived in")
    print("    anything you publish.")

except TierRequiredError as exc:
    print("\nYour plan does not include one of these datasets: %s" % exc)
    print("required tier: %s" % (exc.required_tier or "see the dataset page"))
except MissingApiKeyError as exc:
    print("\nNo API key configured, so this example cannot run: %s" % exc)
    print("\nCorrect behaviour -- these datasets are starter/pro/max. Set")
    print("TWMD_API_KEY and re-run.")
