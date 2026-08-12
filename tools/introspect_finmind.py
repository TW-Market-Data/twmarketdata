"""Signature-only introspection of the installed FinMind package.
Reads public method signatures to build an interop mapping table.
Does NOT call the FinMind service, does not use credentials, does not copy source.
"""
import inspect, json, importlib.metadata as md

import FinMind
from FinMind.data import DataLoader

ver = md.version("FinMind")
out = {"package": "FinMind", "version": ver, "methods": []}

for name, fn in inspect.getmembers(DataLoader, predicate=inspect.isfunction):
    if name.startswith("_"):
        continue
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        continue
    params = [
        {"name": p.name,
         "kind": str(p.kind),
         "default": None if p.default is inspect._empty else repr(p.default),
         "annotation": None if p.annotation is inspect._empty else str(p.annotation)}
        for p in sig.parameters.values() if p.name != "self"
    ]
    doc = (inspect.getdoc(fn) or "").strip().splitlines()
    out["methods"].append({"name": name, "params": params,
                           "doc_first_line": doc[0] if doc else ""})

# dataset enum names, if the package exposes one
try:
    from FinMind.schema.data import Dataset
    out["dataset_enum"] = sorted(m.value for m in Dataset)
except Exception as e:
    out["dataset_enum_error"] = str(e)

json.dump(out, open("finmind_introspect.json", "w"), ensure_ascii=False, indent=1)
print("FinMind version:", ver)
print("public DataLoader methods:", len(out["methods"]))
print("dataset enum entries:", len(out.get("dataset_enum", [])))
