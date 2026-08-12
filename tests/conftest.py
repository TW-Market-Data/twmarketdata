"""Offline test doubles.

No test in this file touches the network. The live free-tier checks live in
tests/test_live_free_tier.py behind the ``network`` marker.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional

import pytest


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200,
                 headers: Optional[Mapping[str, str]] = None, url: str = "http://test") -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = dict(headers or {"X-Request-Id": "req_test"})
        self.url = url

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload

    @property
    def text(self) -> str:
        return self._payload if isinstance(self._payload, str) else json.dumps(self._payload)


class FakeSession:
    """Stands in for requests.Session; records calls and replays queued responses."""

    def __init__(self, responses: Optional[List[FakeResponse]] = None) -> None:
        self.headers: Dict[str, str] = {}
        self.queue: List[FakeResponse] = list(responses or [])
        self.calls: List[Dict[str, Any]] = []
        self.default = FakeResponse({"dataset": "test", "rows": [], "count": 0})

    def get(self, url: str, params: Optional[Mapping[str, Any]] = None,
            headers: Optional[Mapping[str, str]] = None, timeout: Any = None) -> FakeResponse:
        self.calls.append({"url": url, "params": dict(params or {}),
                           "headers": dict(headers or {}), "timeout": timeout})
        return self.queue.pop(0) if self.queue else self.default

    def close(self) -> None:
        pass


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(session: FakeSession):
    from twmd import Client
    c = Client(session=session, max_retries=0)
    c._transport._sleep = lambda _s: None  # no real sleeping in tests
    return c


def rows_envelope(rows: List[Dict[str, Any]], key: str = "rows", **extra: Any) -> Dict[str, Any]:
    return {"dataset": "test", key: rows, "count": len(rows), **extra}
