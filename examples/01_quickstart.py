"""Two lines to a DataFrame. No API key.

    python examples/01_quickstart.py

Uses 2330 (TSMC), one of the five free-tier demo symbols.
"""
from twmd import Client

df = Client().daily_price("2330")

print(df.head())
print()
print("rows:", len(df))
print("meta:", df.twmd)
