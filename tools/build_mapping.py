#!/usr/bin/env python3
"""Regenerate mapping/datasets_82.csv and mapping/finmind_map.csv from raw evidence.

Inputs (all under mapping/sources/, all fetched 2026-08-12):
  twmd_openapi.json          GET https://api.twmarketdata.com/openapi.json
  twmd_v2_datasets.json      GET https://api.twmarketdata.com/v2/datasets
  twmd_schemas_82.json       GET /v2/datasets/{dataset_key}/schema for each of the 82
  twmd_pit_facts.py          transcription of twmd.describe_dataset (MCP), one call per dataset
  finmind_introspect.json    signature introspection of FinMind v2.0.7
  smoke_nokey.json           no-key probe of every route (free-tier reachability)

Nothing here calls a paid endpoint and nothing here needs an API key.
"""
import csv, json, os, sys, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "mapping", "sources")
OUT = os.path.join(ROOT, "mapping")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finmind_mapping_data import MAPPINGS, TWMD_ONLY, FINMIND_VERSION, INTROSPECTED_ON  # noqa: E402

TIER_LABEL = {
    "A": "A_one_to_one", "B": "B_transformed", "C": "C_substituted",
    "D": "D_unavailable", "E": "E_twmd_only",
}


def load(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as fh:
        return json.load(fh)


def load_pit():
    path = os.path.join(SRC, "twmd_pit_facts.py")
    spec = importlib.util.spec_from_file_location("twmd_pit_facts", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PIT


# Canonical SDK parameter names -> the per-route names the live API actually uses.
ENTITY_PARAMS = ["ticker", "symbol", "entity_id", "cb_id", "contract", "contract_code",
                 "index_code", "issuer", "underlying_ticker", "bond_code"]
START_PARAMS = ["date_from", "start_date", "start_month", "start_period", "data_month",
                "trade_date", "settlement_date"]
END_PARAMS = ["date_to", "end_date", "end_month", "end_period"]
ASOF_PARAMS = ["as_of", "as_of_date", "source_as_of_date"]
HOUSEKEEPING = {"limit", "offset", "include_data_gaps", "sort_by", "sort_order"}

# Filters the server demands but the OpenAPI does not declare. Both routes answer
# 400 missing_required_filter without naming the field, so these were found by
# probing on 2026-08-12. Each entry lists filter sets that were observed to work.
REQUIRED_FILTERS = {
    "interest_rate_snapshots": ["rate_family", "rate_code"],
    "market_breadth": ["market", "date_from+date_to"],
}


def build_datasets_csv():
    oapi = load("twmd_openapi.json")["paths"]
    registry = {d["dataset_key"]: d for d in load("twmd_v2_datasets.json")["datasets"]}
    schemas = load("twmd_schemas_82.json")
    smoke = load("smoke_nokey.json")
    pit = load_pit()

    rows = []
    for key, (zh, cat, tier, slug, ktf, pit_safe, has_note, grain) in pit.items():
        route = "/v2/datasets/" + slug
        params_spec = oapi.get(route, {}).get("get", {}).get("parameters", [])
        qp = [p["name"] for p in params_spec if p.get("in") == "query"]
        # The row cap is per route, not global: five different maxima are in use
        # (100 / 500 / 1000 / 2000 / 5000). Sending more returns 422 on some
        # routes and is silently clamped on others.
        limit_spec = next((p for p in params_spec if p.get("name") == "limit"), {})
        limit_max = (limit_spec.get("schema") or {}).get("maximum")
        reg = registry.get(key, {})
        cols = [c["column_name"] for c in (schemas.get(key, {}).get("schema") or [])]
        probe = smoke.get(key, {})

        server_asof = next((p for p in ASOF_PARAMS if p in qp), None)
        as_of_note = ""
        if not ktf and not pit_safe:
            # describe_dataset declares no knowledge axis AND not point-in-time safe.
            # Some of these routes still ACCEPT an as_of parameter -- accepting it would let the
            # caller believe a replay happened. Semantics beat the parameter list: refuse.
            as_of_mode = "unsupported"
            if server_asof:
                as_of_note = ("route accepts %s but describe_dataset declares no knowledge axis "
                              "and point_in_time_safe=false; SDK refuses as_of" % server_asof)
            else:
                as_of_note = "no knowledge axis; as_of refused by design"
        elif server_asof:
            as_of_mode = "server"
        elif ktf and not pit_safe:
            # A knowledge field is declared, but describe_dataset says the dataset is NOT
            # point-in-time safe -- i.e. the field you would naturally align on is not a
            # knowledge axis (it is a period, an effective date, or an observation date).
            # Filtering locally on it would reintroduce exactly the look-ahead that as_of
            # exists to prevent, so the SDK refuses by default and requires an explicit
            # as_of_policy="declared_field" opt-in.
            as_of_mode = "client_unsafe"
            as_of_note = ("knowledge field '%s' declared but point_in_time_safe=false; local "
                          "filtering on it may look ahead, so as_of is refused unless the caller "
                          "opts in explicitly" % ktf)
        elif ktf and ktf in cols:
            as_of_mode = "client"
        elif ktf:
            # a knowledge field is declared but does not appear in the published schema:
            # the SDK must not claim it can filter on it until that is resolved.
            as_of_mode = "client_unverified"
            as_of_note = ("knowledge field '%s' declared but absent from the published schema; "
                          "SDK verifies at runtime" % ktf)
        else:
            as_of_mode = "unsupported"
            as_of_note = "no knowledge axis declared"

        # Honest probe labelling. A 403 temporarily_blocked means OUR OWN probe tripped the
        # rate limiter, so it says nothing about whether the dataset is free-tier reachable.
        # It must not be recorded as "needs key".
        http = probe.get("http")
        if http == 200 and probe.get("rows", 0) > 0:
            free_probe = "yes_rows"
        elif http == 200:
            free_probe = "yes_empty"
        elif http == 401:
            free_probe = "needs_key"
        elif http == 403 and probe.get("error") == "temporarily_blocked":
            free_probe = "unknown_rate_limited"
        else:
            free_probe = f"unknown_http_{http}"

        rows.append({
            "dataset_key": key,
            "sdk_method": key,
            "name_zh": zh,
            "category": cat,
            "tier": tier,
            "route": route,
            "route_equals_kebab_key": "yes" if slug == key.replace("_", "-") else "NO",
            "registry_status": reg.get("status", ""),
            "grain": grain,
            "knowledge_time_field": ktf or "",
            "point_in_time_safe": str(bool(pit_safe)).lower(),
            "pit_caveat_documented": "yes" if has_note else "",
            "as_of_mode": as_of_mode,
            "as_of_param": server_asof or "",
            "as_of_note": as_of_note,
            "data_gaps_param": "include_data_gaps" if "include_data_gaps" in qp else "",
            "pagination": "offset" if "offset" in qp else "limit_only",
            "limit_max": limit_max or "",
            "required_filters": "|".join(REQUIRED_FILTERS.get(key, [])),
            "api_entity_param": next((p for p in ENTITY_PARAMS if p in qp), ""),
            "api_start_param": next((p for p in START_PARAMS if p in qp), ""),
            "api_end_param": next((p for p in END_PARAMS if p in qp), ""),
            "api_other_params": "|".join(
                p for p in qp
                if p not in ENTITY_PARAMS + START_PARAMS + END_PARAMS + ASOF_PARAMS
                and p not in HOUSEKEEPING),
            "n_columns": len(cols),
            "free_tier_probe_2026_08_12": free_probe,
            "coverage_min": reg.get("min_period") or "",
            "coverage_max": reg.get("max_period") or "",
            "entity_count": reg.get("entity_count") or "",
            "row_count": reg.get("row_count") or "",
            "source_name": reg.get("source_name") or "",
            "quality_status": reg.get("quality_status") or "",
            "columns": "|".join(cols),
        })

    rows.sort(key=lambda r: (r["category"] or "zz_uncategorised", r["dataset_key"]))
    path = os.path.join(OUT, "datasets_82.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows, path


def build_finmind_csv():
    fm = load("finmind_introspect.json")
    known_methods = {m["name"] for m in fm["methods"]}
    known_datasets = set(fm.get("dataset_enum", []))
    params = {m["name"]: [p["name"] for p in m["params"]] for m in fm["methods"]}

    rows = []
    for method, ds_enum, tier, twmd, confidence, note in MAPPINGS:
        bare = method.strip("()")
        # A method name in parentheses means: the dataset exists in the enum but is reached
        # via get_data(dataset=...) rather than a dedicated DataLoader method.
        if method.startswith("("):
            verified = "dataset_enum" if ds_enum in known_datasets else "UNVERIFIED"
            sig = "get_data(dataset=%s, ...)" % ds_enum
        else:
            verified = "method_signature" if bare in known_methods else "UNVERIFIED"
            sig = "%s(%s)" % (bare, ", ".join(params.get(bare, [])))
        rows.append({
            "finmind_method": method,
            "finmind_dataset": ds_enum,
            "finmind_signature": sig,
            "finmind_verified_by": verified,
            "mapping_tier": TIER_LABEL[tier],
            "twmd_dataset": twmd,
            "compat_behaviour": {
                "A": "return mapped frame",
                "B": "reshape, mark mapping=transformed",
                "C": "return substitute + CompatSubstitutionWarning",
                "D": "raise NotMappedError (never an empty frame)",
            }[tier],
            "confidence": confidence,
            "note": note,
            "finmind_source": "introspection of FinMind v%s @ %s" % (FINMIND_VERSION, INTROSPECTED_ON),
        })

    for ds, why in TWMD_ONLY:
        rows.append({
            "finmind_method": "",
            "finmind_dataset": "",
            "finmind_signature": "",
            "finmind_verified_by": "no_entry_in_introspected_surface",
            "mapping_tier": TIER_LABEL["E"],
            "twmd_dataset": ds,
            "compat_behaviour": "n/a - reachable via the native twmd client",
            "confidence": "high",
            "note": why,
            "finmind_source": "introspection of FinMind v%s @ %s" % (FINMIND_VERSION, INTROSPECTED_ON),
        })

    path = os.path.join(OUT, "finmind_map.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows, fm, path


def main():
    ds_rows, ds_path = build_datasets_csv()
    fm_rows, fm, fm_path = build_finmind_csv()

    from collections import Counter
    print("wrote %s (%d rows)" % (ds_path, len(ds_rows)))
    for field in ("tier", "as_of_mode", "pagination", "registry_status",
                  "api_entity_param", "api_start_param", "free_tier_probe_2026_08_12"):
        print("   %-28s %s" % (field, dict(Counter(r[field] for r in ds_rows))))
    print("   route_equals_kebab_key NO:",
          [r["dataset_key"] for r in ds_rows if r["route_equals_kebab_key"] == "NO"])

    print("\nwrote %s (%d rows)" % (fm_path, len(fm_rows)))
    print("   tiers      %s" % dict(Counter(r["mapping_tier"] for r in fm_rows)))
    print("   confidence %s" % dict(Counter(r["confidence"] for r in fm_rows)))
    print("   finmind side verified: %s" % dict(Counter(r["finmind_verified_by"] for r in fm_rows)))

    unver = [r["finmind_method"] or r["finmind_dataset"]
             for r in fm_rows if r["finmind_verified_by"] == "UNVERIFIED"]
    if unver:
        print("   !! UNVERIFIED finmind entries (fix before shipping): %s" % unver)

    mapped = {t for r in fm_rows for t in r["twmd_dataset"].split("+") if t}
    all_ds = {r["dataset_key"] for r in ds_rows}
    print("\n   TWMD datasets referenced by the compat layer: %d/82" % len(mapped & all_ds))
    print("   referenced but not in the 82:", sorted(mapped - all_ds) or "none")
    print("   in the 82 but never referenced:", len(all_ds - mapped))


if __name__ == "__main__":
    main()
