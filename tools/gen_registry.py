#!/usr/bin/env python3
"""Generate twmd/_registry.json from mapping/datasets_82.csv.

The registry is what lets one generic HTTP call serve 82 datasets whose routes,
parameter names, pagination and point-in-time semantics all differ. It is
generated, never hand-edited: rerun tools/build_mapping.py first if the live API
has changed, then rerun this.
"""
import csv, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "mapping", "datasets_82.csv")
OUT = os.path.join(ROOT, "twmd", "_registry.json")

# Kept in the shipped registry; everything else in the CSV is documentation.
FIELDS = [
    "name_zh", "category", "tier", "route", "registry_status", "grain",
    "knowledge_time_field", "point_in_time_safe", "as_of_mode", "as_of_param",
    "as_of_note", "data_gaps_param", "pagination", "api_entity_param",
    "api_start_param", "api_end_param", "api_other_params",
    "free_tier_probe_2026_08_12", "coverage_min", "coverage_max", "columns",
]


def main() -> None:
    with open(CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    datasets = {}
    for r in rows:
        entry = {}
        for f in FIELDS:
            v = r.get(f, "")
            if f == "point_in_time_safe":
                entry["point_in_time_safe"] = (v == "true")
            elif f == "pagination":
                entry["supports_offset"] = (v == "offset")
            elif f == "data_gaps_param":
                entry["supports_data_gaps"] = bool(v)
            elif f == "free_tier_probe_2026_08_12":
                entry["free_tier_probe"] = v
            elif f in ("columns", "api_other_params", "grain"):
                entry[f] = [x for x in v.split("|") if x]
            else:
                entry[f] = v or None
        datasets[r["dataset_key"]] = entry

    payload = {
        "schema_version": 1,
        "generated_from": "mapping/datasets_82.csv",
        "measured_on": "2026-08-12",
        "api_base_url": "https://api.twmarketdata.com/v2",
        "sources": [
            "GET https://api.twmarketdata.com/v2/datasets",
            "GET https://api.twmarketdata.com/openapi.json",
            "GET https://api.twmarketdata.com/v2/datasets/{dataset_key}/schema",
            "twmd.describe_dataset (MCP), one call per dataset",
        ],
        "free_tier_symbols": ["2330", "2317", "2454", "0050", "2603"],
        "dataset_count": len(datasets),
        "datasets": datasets,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")

    from collections import Counter
    print("wrote %s (%d datasets)" % (OUT, len(datasets)))
    print("  as_of_mode      ", dict(Counter(d["as_of_mode"] for d in datasets.values())))
    print("  offset support  ", sum(1 for d in datasets.values() if d["supports_offset"]))
    print("  data_gaps param ", sum(1 for d in datasets.values() if d["supports_data_gaps"]))
    print("  free probe      ", dict(Counter(d["free_tier_probe"] for d in datasets.values())))


if __name__ == "__main__":
    main()
