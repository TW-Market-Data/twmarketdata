"""The pre-publish secret gate must stay strict.

It fired on all 63 recorded cassettes because its own redaction marker,
``"X-API-Key": "REDACTED"``, matched the unredacted-header pattern. The marker
is now exempt -- and these tests exist so that exemption cannot quietly widen
into "any header value is fine".

The fixtures below are assembled from fragments rather than written as literals,
so this file does not itself trip the gate. That is deliberate: the audit
exempts exactly one path (its own source), and adding a second exemption would
be a hole that grows.
"""
from __future__ import annotations

import re

import pytest

from tools.audit_public_repo import SECRET_PATTERNS

LIVE = "sk_" + "live_0123456789abcdef"
TEST = "sk_" + "test_0123456789abcdef"
VALUE = "abcdefgh12345678"
BEARER = "Bearer " + "abcdefghijklmnopqrstuvwx"
PRIVKEY = "-----BEGIN " + "PRIVATE KEY-----"


def _hits(text: str):
    return [label for pattern, label in SECRET_PATTERNS if re.search(pattern, text)]


def test_redaction_marker_is_not_a_finding():
    assert _hits('"X-API-Key": "REDACTED"') == []
    assert _hits('"Authorization": "REDACTED"') == []


@pytest.mark.parametrize("line", [
    '"X-API-Key": "%s"' % LIVE,
    '"X-API-Key": "%s"' % VALUE,
    "X-API-KEY=%s" % VALUE,               # unquoted form
    '"authorization": "%s"' % BEARER,
])
def test_real_headers_are_still_caught(line):
    assert _hits(line), "the gate stopped catching %r" % line


@pytest.mark.parametrize("value", [LIVE, TEST, PRIVKEY])
def test_key_shapes_are_still_caught(value):
    assert _hits(value)


def test_a_value_that_merely_starts_with_redacted_is_still_caught():
    # Exempting a prefix rather than the whole value would be a hole.
    assert _hits('"X-API-Key": "REDACTED%s"' % LIVE)


def test_test_fixture_placeholder_stays_allowed():
    assert _hits("sk_" + "test_notreal") == []


def test_recorded_cassettes_carry_only_the_marker():
    """Every committed cassette must have a redacted auth header."""
    import glob
    import json
    cassettes = sorted(glob.glob("tests/cassettes/*.json"))
    if not cassettes:
        pytest.skip("no cassettes recorded yet")
    for path in cassettes:
        with open(path, encoding="utf-8") as fh:
            body = json.load(fh)
        assert body["request"]["headers"] == {"X-API-Key": "REDACTED"}, path
        assert _hits(open(path, encoding="utf-8").read()) == [], path


# ------------------------------------------------------------ packaging
def test_every_package_directory_with_data_files_is_declared():
    """A package-data key covers only its own package.

    twmd.compat was missing from the declaration, so the built wheel omitted
    _finmind_map.json and `from twmd.compat import finmind` raised
    FileNotFoundError on import. Caught by the wheel audit, not by any test that
    ran from the source tree -- which is the whole point of building before
    publishing.
    """
    import os
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    declared = set(re.findall(r'^"?([\w.]+)"?\s*=\s*\[',
                              open(os.path.join(root, "pyproject.toml"),
                                   encoding="utf-8").read().split(
                                       "[tool.setuptools.package-data]")[1].split("[")[0],
                              re.M))
    needs_data = set()
    for dirpath, _dirnames, filenames in os.walk(os.path.join(root, "twmd")):
        if any(f.endswith((".json", ".pyi")) or f == "py.typed" for f in filenames):
            rel = os.path.relpath(dirpath, root).replace(os.sep, ".")
            needs_data.add(rel)
    assert needs_data <= declared, (
        "package(s) ship data files but are not in [tool.setuptools.package-data]: %s"
        % sorted(needs_data - declared))
