#!/usr/bin/env python3
"""Generate twmd/compat/_finmind_map.json from mapping/finmind_map.csv.

Keeps the shipped compat behaviour and the reviewed mapping table as one source
of truth: change the table, regenerate, and the runtime follows.
"""
import csv, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "mapping", "finmind_map.csv")
OUT = os.path.join(ROOT, "twmd", "compat", "_finmind_map.json")

TIER = {
    "A_one_to_one": "A", "B_transformed": "B", "C_substituted": "C",
    "D_unavailable": "D", "E_twmd_only": "E",
}


def main():
    with open(CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    methods, source = {}, None
    for r in rows:
        source = source or r["finmind_source"]
        tier = TIER[r["mapping_tier"]]
        if tier == "E":
            continue
        name = r["finmind_method"].strip()
        if not name:
            continue
        bare = name.strip("()")
        methods[bare] = {
            "tier": tier,
            "twmd": [d for d in r["twmd_dataset"].split("+") if d],
            "confidence": r["confidence"],
            "note": r["note"],
            "dataset_enum": r["finmind_dataset"],
            "via_get_data_only": name.startswith("("),
            "verified_by": r["finmind_verified_by"],
        }

    payload = {
        "schema_version": 1,
        "finmind_source": source,
        "method_count": len(methods),
        "methods": methods,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    from collections import Counter
    print("wrote %s (%d methods)" % (OUT, len(methods)))
    print("  tiers      ", dict(Counter(m["tier"] for m in methods.values())))
    print("  confidence ", dict(Counter(m["confidence"] for m in methods.values())))


if __name__ == "__main__":
    main()
