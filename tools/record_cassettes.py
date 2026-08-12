#!/usr/bin/env python3
"""Record paid-tier responses as replayable cassettes. One command, auto-redacted.

    export TWMD_API_KEY=<restricted key>
    python tools/record_cassettes.py

Writes ``tests/cassettes/<dataset>.json`` for every dataset that needs a key, so
the test suite can exercise paid-tier behaviour in CI without one. Delete the
restricted key from the console afterwards.

SECRETS
    The key is read from the environment only -- never a flag, never a file, so
    it cannot end up in shell history or a diff. Before anything is written:

    * request headers are dropped entirely except a redacted ``X-API-Key``
    * every recorded byte is scanned for the key's literal value and for
      ``sk_live_`` / ``sk_test_`` patterns
    * a cassette that still matches after redaction is NOT written, and the run
      fails

    ``tools/audit_public_repo.py`` re-checks the whole tree afterwards, so a
    leak has to get past two independent gates.

PACING
    One request every few seconds. Fast probing returns 403 temporarily_blocked
    and the block persists for tens of minutes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CASSETTE_DIR = os.path.join(ROOT, "tests", "cassettes")
REDACTED = "REDACTED"
SECRET_PATTERNS = [
    re.compile(r"sk_live_[A-Za-z0-9_\-]{4,}"),
    re.compile(r"sk_test_(?!notreal)[A-Za-z0-9_\-]{8,}"),
]

DEMO_TICKER = "2330"
PACE_SECONDS = 3.0

#: A working value for each undeclared-but-required filter (measured 2026-08-12).
REQUIRED_FILTER_EXAMPLES = {
    "interest_rate_snapshots": {"rate_family": "policy"},
    "market_breadth": {"market": "TWSE"},
}


def _redact(blob: str, key: Optional[str]) -> str:
    if key:
        blob = blob.replace(key, REDACTED)
    for pattern in SECRET_PATTERNS:
        blob = pattern.sub(REDACTED, blob)
    return blob


def _contains_secret(blob: str, key: Optional[str]) -> bool:
    if key and key in blob:
        return True
    return any(p.search(blob) for p in SECRET_PATTERNS)


def record_one(client: Any, dataset: str, key: Optional[str]) -> Optional[Dict[str, Any]]:
    """Fetch one dataset and return a redacted cassette, or None on failure."""
    from twmd import registry
    from twmd.errors import TwmdError

    info = registry.get(dataset)
    kwargs: Dict[str, Any] = {"limit": 5, "raw": True}
    if info.entity_param:
        kwargs["ticker"] = DEMO_TICKER
    # Two routes demand a filter the OpenAPI does not declare; without it they
    # answer 400 and the cassette records an error instead of data.
    for example in REQUIRED_FILTER_EXAMPLES.get(dataset, {}).items():
        kwargs[example[0]] = example[1]

    try:
        payload = client.dataset(dataset, **kwargs)
        status = 200
        error = None
    except TwmdError as exc:
        # A 402/403 is a real recording too: it pins how the SDK classifies the
        # plan boundary for this key.
        payload = dict(exc.details) if exc.details else {"error": exc.error_code}
        status = exc.status_code or 0
        error = type(exc).__name__

    cassette = {
        "dataset": dataset,
        "route": info.route,
        "request": {
            "method": "GET",
            "params": {k: v for k, v in kwargs.items() if k != "raw"},
            "headers": {"X-API-Key": REDACTED},
        },
        "response": {"status": status, "body": payload},
        "recorded_with": "restricted test key (value never stored)",
        "sdk_error": error,
    }

    blob = json.dumps(cassette, ensure_ascii=False)
    blob = _redact(blob, key)
    if _contains_secret(blob, key):
        print("  !! %s: secret survived redaction -- NOT written" % dataset)
        return None
    return json.loads(blob)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", nargs="*", help="defaults to every key-gated dataset")
    parser.add_argument("--pace", type=float, default=PACE_SECONDS)
    parser.add_argument("--limit-count", type=int, default=0,
                        help="record at most N datasets (0 = no cap)")
    args = parser.parse_args()

    key = os.environ.get("TWMD_API_KEY")
    if not key:
        print("TWMD_API_KEY is not set.\n\n"
              "Generate a RESTRICTED key in the console, export it in your own shell,\n"
              "run this, then delete the key. Never pass it as a flag and never paste\n"
              "it into a chat or a file.")
        return 2

    import twmd
    from twmd import registry

    targets: List[str] = args.datasets or [
        k for k in registry.datasets()
        if registry.get(k).free_tier_probe == "needs_key"
    ]
    if args.limit_count:
        targets = targets[: args.limit_count]

    os.makedirs(CASSETTE_DIR, exist_ok=True)
    client = twmd.Client(max_concurrency=1)

    written, failed = 0, []
    print("recording %d dataset(s), one every %.1fs" % (len(targets), args.pace))
    for i, dataset in enumerate(targets, 1):
        cassette = record_one(client, dataset, key)
        if cassette is None:
            failed.append(dataset)
        else:
            path = os.path.join(CASSETTE_DIR, "%s.json" % dataset)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cassette, fh, ensure_ascii=False, indent=1, sort_keys=True)
                fh.write("\n")
            written += 1
            status = cassette["response"]["status"]
            body = cassette["response"]["body"]
            from twmd.envelope import extract_rows
            extracted, row_key = extract_rows(body)
            print("  [%2d/%2d] %-34s %s rows=%d via %s"
                  % (i, len(targets), dataset, status, len(extracted), row_key or "-"))
        time.sleep(args.pace)
    client.close()

    print("\nwrote %d cassette(s) to %s" % (written, os.path.relpath(CASSETTE_DIR, ROOT)))
    if failed:
        print("FAILED redaction (not written): %s" % ", ".join(failed))

    print("\nverifying the whole tree...")
    from tools.audit_public_repo import main as audit  # type: ignore
    if audit() != 0:
        return 1
    print("\nNext: delete the restricted key in the console, then commit the cassettes.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
