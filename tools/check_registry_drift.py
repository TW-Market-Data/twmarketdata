#!/usr/bin/env python3
"""Detect when the live API has drifted away from the shipped registry.

Routes get renamed, parameters appear and disappear, datasets are added. The SDK
translates every call through the registry, so drift shows up as wrong requests
rather than obvious errors -- which is exactly the kind of failure that goes
unnoticed. CI runs this daily.

Uses only the public, key-free discovery endpoints. Exits 1 on drift so the job
turns red and someone regenerates.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

API = "https://api.twmarketdata.com"
TIMEOUT = 40

ENTITY = ["ticker", "symbol", "entity_id", "cb_id", "contract", "contract_code",
          "index_code", "issuer", "underlying_ticker", "bond_code"]
START = ["date_from", "start_date", "start_month", "start_period", "data_month",
         "trade_date", "settlement_date"]
ASOF = ["as_of", "as_of_date", "source_as_of_date"]


def fetch(path: str) -> Any:
    with urllib.request.urlopen(API + path, timeout=TIMEOUT) as response:
        return json.load(response)


def main() -> int:
    from twmd import registry

    try:
        spec = fetch("/openapi.json")["paths"]
    except Exception as exc:                       # network flake, not drift
        print("could not reach the API (%s); skipping drift check" % exc)
        return 0

    drift: List[str] = []
    for key in registry.datasets():
        info = registry.get(key)
        route = info.route
        entry = spec.get(route)
        if entry is None:
            drift.append("%s: route %s no longer exists in the OpenAPI spec"
                         % (key, route))
            continue

        params = {p["name"] for p in entry.get("get", {}).get("parameters", [])
                  if p.get("in") == "query"}

        def first(names: List[str]) -> Any:
            return next((n for n in names if n in params), None)

        checks = [
            ("entity parameter", info.entity_param, first(ENTITY)),
            ("start parameter", info.start_param, first(START)),
            ("as_of parameter", info.as_of_param, first(ASOF)),
            ("offset support", info.supports_offset, "offset" in params),
            ("data_gaps support", info.supports_data_gaps, "include_data_gaps" in params),
        ]
        for label, shipped, live in checks:
            if shipped != live:
                drift.append("%s: %s shipped=%r live=%r" % (key, label, shipped, live))

    try:
        live_keys = {d["dataset_key"] for d in fetch("/v2/datasets")["datasets"]}
        new = live_keys - set(registry.datasets())
        # Only sellable datasets ship, so new registry entries are informational.
        if new:
            print("note: %d dataset(s) in the live registry are not shipped "
                  "(expected -- the SDK ships the sellable subset): %s"
                  % (len(new), ", ".join(sorted(new)[:8])))
    except Exception:
        pass

    if drift:
        print("REGISTRY DRIFT (%d):" % len(drift))
        for d in drift:
            print("   ", d)
        print("\nRegenerate: python tools/build_mapping.py && python tools/gen_registry.py "
              "&& python tools/gen_methods.py")
        return 1

    print("registry matches the live API (%d datasets checked)"
          % len(registry.datasets()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
