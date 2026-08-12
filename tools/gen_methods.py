#!/usr/bin/env python3
"""Generate twmd/_methods.py (+ .pyi) -- one named method per sellable dataset.

Generated, not hand-written, so a dataset cannot be silently missed and every
signature reflects the parameters that route actually accepts. Method names use
the stable ``dataset_key``, never the route slug: six routes are not the
kebab-case of their key and route names can drift.
"""
import json, os, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "twmd", "_registry.json")
OUT = os.path.join(ROOT, "twmd", "_methods.py")
OUT_PYI = os.path.join(ROOT, "twmd", "_methods.pyi")

HEADER = '''"""Generated dataset methods -- do not edit by hand.

Regenerate with::

    python tools/build_mapping.py && python tools/gen_registry.py && python tools/gen_methods.py

Every method here is a thin call through to :meth:`twmd.Client.dataset`, which
does the parameter translation, pagination, point-in-time handling and gap
reporting. The value of the named methods is discoverability and typing.
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = ["DatasetMethods"]


class DatasetMethods:
    """Mixin providing one method per sellable dataset ({n} of them)."""

'''

PYI_HEADER = '''from typing import Any, Optional

class DatasetMethods:
'''


def build_method(key, d):
    parts, call, doc_args = [], [], []
    if d.get("api_entity_param"):
        parts.append("ticker: Optional[str] = None")
        call.append("ticker=ticker")
        doc_args.append("ticker: security id (sent as %r)" % d["api_entity_param"])
    if d.get("api_start_param"):
        parts.append("start: Optional[str] = None")
        call.append("start=start")
        doc_args.append("start: sent as %r" % d["api_start_param"])
    if d.get("api_end_param"):
        parts.append("end: Optional[str] = None")
        call.append("end=end")
        doc_args.append("end: sent as %r" % d["api_end_param"])
    if d["as_of_mode"] != "unsupported":
        parts.append("as_of: Optional[str] = None")
        call.append("as_of=as_of")
    parts += ["limit: Optional[int] = None", "raw: bool = False"]
    call += ["limit=limit", "raw=raw"]

    sig = "self, *, " + ", ".join(parts) + ", **extra: Any"
    body_call = "return self.dataset(%r, %s, **extra)" % (key, ", ".join(call))

    zh = d.get("name_zh") or key
    first = "%s -- tier=%s, status=%s." % (zh, d["tier"], d["registry_status"])

    lines = [first, ""]
    if d.get("grain"):
        lines.append("Grain: one row per (%s)." % ", ".join(d["grain"]))
    lines.append("Route: %s" % d["route"])
    lines.append("as_of: %s. data_gaps: %s. pagination: %s."
                 % (d["as_of_mode"],
                    "server" if d["supports_data_gaps"] else "not on this route",
                    "offset" if d["supports_offset"] else "limit only"))
    if d["free_tier_probe"] == "yes_rows":
        lines.append("Runs without an API key on the demo symbols.")
    elif d["free_tier_probe"] == "needs_key":
        lines.append("Requires an API key (measured: 401 without one).")
    if d.get("as_of_note"):
        lines.append("")
        lines += textwrap.wrap("PIT note: " + d["as_of_note"], 74)
    if doc_args:
        lines.append("")
        lines.append("Args:")
        lines += ["    " + a for a in doc_args]

    doc = "\n".join("        " + ln if ln else "" for ln in lines)
    method = (
        "    def %s(%s) -> Any:\n"
        '        """%s\n        """\n'
        "        %s\n\n" % (key, sig, doc.strip(), body_call)
    )
    stub = "    def %s(%s) -> Any: ...\n" % (key, sig)
    return method, stub


def main():
    with open(REG, encoding="utf-8") as fh:
        reg = json.load(fh)
    datasets = reg["datasets"]

    methods, stubs = [], []
    for key in sorted(datasets):
        m, s = build_method(key, datasets[key])
        methods.append(m)
        stubs.append(s)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(HEADER.format(n=len(datasets)))
        fh.write("".join(methods))

    with open(OUT_PYI, "w", encoding="utf-8") as fh:
        fh.write(PYI_HEADER)
        fh.write("".join(stubs))

    print("wrote %s (%d methods)" % (OUT, len(methods)))
    print("wrote %s" % OUT_PYI)


if __name__ == "__main__":
    main()
