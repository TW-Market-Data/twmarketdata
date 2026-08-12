"""Point-in-time fundamentals for a backtest.  (tier=pro — API key required)

    TWMD_API_KEY=<your key> python examples/03_backtest_ready_fundamentals.py

Run against the live API on 2026-08-12 with a restricted key. Without a key you
get MissingApiKeyError, which is the honest outcome -- this file is not runnable
on the free tier and does not pretend to be.

Real output from that run, for 2330 with as_of=2023-06-30:

    income_statement rows knowable on 2023-06-30: 42
      as_of mode      : server (applied=True)
      ⚠ imputed rows  : 42 (statutory_deadline)

Every one of those 42 rows carries kd_imputed=true. The API now returns a
knowledge_date for the fundamentals, but 100% of them are derived from the
statutory filing deadline rather than observed from an announcement -- so the
SDK warns, and this example prints the count rather than quietly using them.

Why these datasets are the interesting case for point-in-time: quarterly
statements are exactly where look-ahead creeps into a backtest. A statement for
Q2 does not exist on the market until it is filed, so aligning on the period end
date silently gives your strategy months of foresight.
"""
import twmd
from twmd import Client
from twmd.errors import MissingApiKeyError

TICKER = "2330"
AS_OF = "2023-06-30"

c = Client()  # reads TWMD_API_KEY

print("=" * 74)
print("Point-in-time mode per dataset (from the registry, no request needed)")
print("=" * 74)
for key in ("income_statement", "balance_sheet", "financial_ratios", "monthly_revenue"):
    caps = twmd.capabilities(key)
    print("%-20s as_of=%-18s pit_safe=%-6s tier=%s"
          % (key, caps["as_of"], caps["point_in_time_safe"], caps["tier"]))

print("""
income_statement / balance_sheet / financial_ratios are `server` mode: the route
takes as_of and filters server-side. monthly_revenue is `client_unsafe` and
refuses as_of by default -- see examples/02_point_in_time.py for why.
""")

try:
    print("=" * 74)
    print("Statements as known on %s" % AS_OF)
    print("=" * 74)
    income = c.income_statement(ticker=TICKER, as_of=AS_OF)
    print("income_statement rows knowable on %s: %d" % (AS_OF, len(income)))
    m = income.twmd
    print("  as_of mode      : %s (applied=%s)" % (m.as_of_mode, m.as_of_applied))
    print("  knowledge field : %s" % m.knowledge_time_field)
    print("  truncated       : %s" % m.truncated)
    print("  gaps            : %d (source=%s)" % (len(m.data_gaps), m.gaps_source))
    if m.knowledge_date_imputed_rows:
        print("  ⚠ imputed rows  : %d (%s)"
              % (m.knowledge_date_imputed_rows, ", ".join(m.knowledge_date_sources)))

    ratios = c.financial_ratios(ticker=TICKER, as_of=AS_OF)
    print("\nfinancial_ratios rows: %d" % len(ratios))
    print("  NOTE: this dataset's route is /v2/datasets/financial-metrics -- the")
    print("  route name and the dataset key differ, which is why the SDK keys")
    print("  methods on dataset_key and looks the route up in the registry.")

    print("""
The point of running with as_of: re-run the same call with as_of one quarter
later and the row count changes. That difference is the look-ahead your backtest
would otherwise have been trading on.""")

except MissingApiKeyError as exc:
    print("\nNo API key configured, so this example cannot run: %s" % exc)
    print("\nThis is the correct behaviour -- these datasets are tier=pro. Set")
    print("TWMD_API_KEY and re-run. Free-tier examples: 01_quickstart.py,")
    print("02_point_in_time.py.")
