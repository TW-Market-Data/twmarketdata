"""What `as_of` does, and what it refuses to do.

    python examples/02_point_in_time.py

No API key needed. Every dataset touched here is on the measured free-tier list.
"""
import warnings

import twmd
from twmd import Client
from twmd.errors import PointInTimeUnavailable

c = Client()

print("=" * 72)
print("1. A dataset where a point-in-time replay is honest")
print("=" * 72)
caps = twmd.capabilities("twse_daily_price")
print("twse_daily_price  as_of=%s  point_in_time_safe=%s  knowledge field=%s"
      % (caps["as_of"], caps["point_in_time_safe"], caps["knowledge_time_field"]))
df = c.twse_daily_price(ticker="2330", start="2026-01-01", as_of="2026-06-30")
print("rows knowable as of 2026-06-30:", len(df))
if len(df):
    print("latest trade_date returned:", max(r for r in df["date"]))

print()
print("=" * 72)
print("2. A dataset the registry calls unsafe -- decided on the response")
print("=" * 72)
caps = twmd.capabilities("monthly_revenue")
print("monthly_revenue   as_of=%s  point_in_time_safe=%s  knowledge field=%s"
      % (caps["as_of"], caps["point_in_time_safe"], caps["knowledge_time_field"]))
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    try:
        df = c.monthly_revenue(ticker="2330", as_of="2026-06-30")
        print("rows knowable on 2026-06-30: %d" % len(df))
        print("field used: %s" % c.last_meta.as_of_field)
        print("latest knowledge_date kept: %s" % max(df["knowledge_date"]))
        for w in caught:
            if "Imputed" in w.category.__name__:
                print("\n  %s: %s" % (w.category.__name__, str(w.message)[:180]))
    except PointInTimeUnavailable as exc:
        print("\nrefused:\n  %s" % exc)

print("""
Why this dataset is special: its DECLARED knowledge field, as_of_date, is the
revenue PERIOD, not the announcement date. June revenue is not disclosed until
July, so filtering on the period would mark it known on June 30 -- the exact
look-ahead as_of exists to prevent. The SDK will not filter on that column.

But the API now supplies a real knowledge_date for this dataset, and a
server-supplied knowledge date outranks the static classification. So the SDK
makes the request, finds it, and answers -- dropping the June figure, whose
knowledge date is 2026-07-10. If the column were absent it would raise instead,
and say that it checked.""")

print("=" * 72)
print("3. Opting in anyway, with eyes open")
print("=" * 72)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    df = c.monthly_revenue(ticker="2330", as_of="2026-06-30",
                           as_of_policy="declared_field")
    for w in caught:
        print("  %s: %s" % (w.category.__name__, str(w.message)[:160]))
print("rows:", len(df))
print("as_of actually applied:", c.last_meta.as_of_applied)
print("field used:", c.last_meta.as_of_field)
print("""
When the API starts returning a knowledge_date column (see
WORKORDER_API_expose_knowledge_date), that column is used instead and this
dataset becomes filterable without the opt-in -- but rows flagged
kd_imputed=true still warn, because a statutory-deadline derivation is a rule,
not an observed disclosure.""")

print("=" * 72)
print("4. Datasets with no knowledge axis at all")
print("=" * 72)
for key in ("company_industry_exposures", "company_peer_groups"):
    try:
        c.dataset(key, as_of="2026-06-30")
    except PointInTimeUnavailable as exc:
        print("%-28s refused" % key)
        print("   %s" % str(exc).split(": ", 1)[1][:150])
