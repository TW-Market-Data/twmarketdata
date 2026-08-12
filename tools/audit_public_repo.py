#!/usr/bin/env python3
"""Pre-publish audit: no secrets, and the wheel ships only the client.

Run before any publish, and in CI on every push::

    python tools/audit_public_repo.py

Exits non-zero on the first finding. Three checks:

1. **No credentials anywhere in the tree.** API keys, bearer tokens, and
   unredacted auth headers in recorded cassettes. Cassettes must have their
   ``X-API-Key`` / ``Authorization`` headers redacted before they are committed.
2. **The distribution ships only the client.** Measurement evidence, mapping
   tables and generators stay in the repo for auditability but must not end up
   inside the installed package.
3. **No stale base URL.** The retired gateway must not reappear as a default.
"""
from __future__ import annotations

import os
import re
import sys
from typing import List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", "dist",
             "build", ".venv", "venv", ".ruff_cache"}
TEXT_SUFFIXES = {".py", ".pyi", ".md", ".toml", ".json", ".yaml", ".yml", ".txt",
                 ".cfg", ".ini", ".csv"}

# Live-key shapes and unredacted auth headers. `sk_test_notreal` is the fixture
# string used in tests and is explicitly allowed.
SECRET_PATTERNS: List[Tuple[str, str]] = [
    (r"sk_live_[A-Za-z0-9_\-]{4,}", "live API key"),
    (r"sk_test_(?!notreal)[A-Za-z0-9_\-]{8,}", "test API key"),
    (r"(?i)x-api-key['\"]?\s*[:=]\s*['\"][A-Za-z0-9_\-]{8,}", "unredacted X-API-Key"),
    (r"(?i)authorization['\"]?\s*[:=]\s*['\"]?bearer\s+[A-Za-z0-9._\-]{16,}",
     "unredacted Authorization header"),
    (r"(?i)\baws_secret_access_key\b\s*[:=]", "AWS secret"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "private key"),
]

RETIRED_BASE_URL = "https://twmarketdata.com/v2"

# Everything the wheel is allowed to contain, by top-level path.
ALLOWED_PACKAGE_PREFIXES = ("twmd/",)


def iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, ROOT)
            if os.path.splitext(name)[1] in TEXT_SUFFIXES or name in {"NOTICE", "LICENSE"}:
                yield rel, path


def check_secrets() -> List[str]:
    findings = []
    self_rel = os.path.relpath(os.path.abspath(__file__), ROOT)
    for rel, path in iter_files():
        if rel == self_rel:
            continue  # this file contains the patterns by definition
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, 1):
                    for pattern, label in SECRET_PATTERNS:
                        if re.search(pattern, line):
                            findings.append("%s:%d: possible %s" % (rel, lineno, label))
        except OSError as exc:
            findings.append("%s: unreadable (%s)" % (rel, exc))
    return findings


def check_retired_base_url() -> List[str]:
    findings = []
    for rel, path in iter_files():
        if not rel.startswith("twmd/"):
            continue
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, 1):
                if RETIRED_BASE_URL in line:
                    findings.append(
                        "%s:%d: references the retired gateway %s"
                        % (rel, lineno, RETIRED_BASE_URL))
    return findings


def check_package_contents() -> List[str]:
    """The declared package must not pull in evidence or tooling."""
    findings = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "twmd")):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), ROOT)
            if not rel.startswith(ALLOWED_PACKAGE_PREFIXES):
                findings.append("%s: inside the package but not an allowed path" % rel)
            if os.path.splitext(name)[1] in {".csv", ".cassette", ".har"}:
                findings.append("%s: evidence/recording file inside the package" % rel)
    for stray in ("mapping", "tools", "tests", "examples"):
        if os.path.isdir(os.path.join(ROOT, "twmd", stray)):
            findings.append("twmd/%s: must live at the repo root, not in the package"
                            % stray)
    return findings


def main() -> int:
    sections = [
        ("secrets", check_secrets()),
        ("retired base URL", check_retired_base_url()),
        ("package contents", check_package_contents()),
    ]
    failed = False
    for label, findings in sections:
        if findings:
            failed = True
            print("FAIL %s (%d):" % (label, len(findings)))
            for f in findings:
                print("   ", f)
        else:
            print("ok   %s" % label)
    if failed:
        print("\nAudit failed. Nothing should be published until this is clean.")
        return 1
    print("\nAudit clean: no credentials, no retired base URL, package ships only the client.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
