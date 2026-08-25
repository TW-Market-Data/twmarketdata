"""`twmd ask` —— 路由到既有的 MCP `ask`,不在 CLI 裡編推斷邏輯。

## 為什麼走 MCP 而不是 REST(實測 2026-08-25)

    /v2/ask     -> 404          `ask` 不在 REST 上
    /v2/search  -> 200 但 kind="docs",查「月營收」回 0 筆 —— 文件搜尋,不是資料集解析器

所以唯一誠實的「路由到既有 ask」就是呼叫那個 MCP 工具。
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from twmd import _cli, _mcp_client


def _run(capsys, argv, **patches):
    for target, value in patches.items():
        pass
    code = _cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ---------------------------------------------------------------------------
# 路由:CLI 不自己猜資料集
# ---------------------------------------------------------------------------

def test_the_question_is_sent_to_the_ask_tool_verbatim(capsys, monkeypatch):
    """⚠️ **這條是「不新編邏輯」的驗收。**

    CLI 不解析問句、不挑資料集 —— 它把整句原樣交給既有的路由。
    在這裡自己猜,會和 MCP 那邊分岔:同一個問題兩個答案,而沒有人會發現。
    """
    seen = {}

    def _fake(name, arguments, **kwargs):
        seen["name"] = name
        seen["arguments"] = dict(arguments)
        return {"rows": [{"month": "2026-07", "revenue": 1}]}

    monkeypatch.setattr(_mcp_client, "call_tool", _fake)
    code, _out, _err = _run(capsys, ["ask", "台積電", "最近三個月的月營收",
                                     "--as-of", "2024-06-30"])
    assert code == _cli.EXIT_OK
    assert seen["name"] == "ask"
    assert seen["arguments"]["question"] == "台積電 最近三個月的月營收"
    assert seen["arguments"]["as_of"] == "2024-06-30"


def test_omitting_as_of_warns_but_still_asks(capsys, monkeypatch):
    monkeypatch.setattr(_mcp_client, "call_tool",
                        lambda *a, **k: {"rows": [{"a": 1}]})
    code, _out, err = _run(capsys, ["ask", "月營收"])
    assert code == _cli.EXIT_OK
    assert "LATEST revision" in err
    assert "as_of" not in json.dumps({})  # 沒有偷偷塞一個預設 as_of 進去


def test_no_default_as_of_is_invented(capsys, monkeypatch):
    """⚠️ 省略時**不要**幫他填今天 —— 那會讓一個沒有時點的問題看起來是有時點的。"""
    seen = {}
    monkeypatch.setattr(_mcp_client, "call_tool",
                        lambda name, arguments, **k: seen.update(arguments) or {"rows": []})
    _run(capsys, ["ask", "月營收"])
    assert "as_of" not in seen


# ---------------------------------------------------------------------------
# 來源
# ---------------------------------------------------------------------------

def test_sources_are_printed(capsys, monkeypatch):
    """一個沒有來源的答案,和一個編出來的答案在讀者眼裡一樣。"""
    monkeypatch.setattr(_mcp_client, "call_tool", lambda *a, **k: {
        "rows": [{"a": 1}], "sources": ["twmd_q_abc123", "monthly_revenue"]})
    _code, _out, err = _run(capsys, ["ask", "月營收"])
    assert "twmd_q_abc123" in err
    assert "sources:" in err


def test_an_unsourced_answer_says_so(capsys, monkeypatch):
    """負向對照:沒有來源時要**明講**,不是安靜地不印。"""
    monkeypatch.setattr(_mcp_client, "call_tool", lambda *a, **k: {"answer": "42"})
    _code, out, err = _run(capsys, ["ask", "月營收"])
    assert "unsourced" in err
    assert "42" in out


def test_sources_go_to_stderr_so_the_data_stays_clean(capsys, monkeypatch):
    """⚠️ 來源走 stderr,資料走 stdout —— `twmd ask … --format json > out.json` 要能解析。"""
    monkeypatch.setattr(_mcp_client, "call_tool", lambda *a, **k: {
        "rows": [{"a": 1}], "sources": ["twmd_q_abc"]})
    _code, out, err = _run(capsys, ["ask", "月營收", "--format", "json"])
    assert "twmd_q_abc" in err
    json.loads(out)          # 多一個位元組就會炸


# ---------------------------------------------------------------------------
# 撞牆:方案問題 vs 設定問題
# ---------------------------------------------------------------------------

def test_a_plan_wall_says_it_is_a_plan_problem_and_no_reconnect(capsys, monkeypatch):
    """⚠️ **接上已拍板的 60 秒模型。**

    講成「access denied」會讓已付費的人反覆檢查金鑰;不講「免重連」則會讓升級完
    的人以為要重設連接器,然後放棄。
    """
    def _blocked(*_a, **_k):
        raise _mcp_client.McpAccessDenied("nope", kind="entitlement")

    monkeypatch.setattr(_mcp_client, "call_tool", _blocked)
    code, _out, err = _run(capsys, ["ask", "月營收"])
    assert code == _cli.EXIT_ENTITLEMENT
    assert "Pro" in err
    assert "do not need to reconnect" in err
    assert "pricing" in err


def test_a_missing_key_is_not_sold_an_upgrade(capsys, monkeypatch):
    """負向對照:沒金鑰是**設定**問題,不該把人送去付費頁。"""
    def _blocked(*_a, **_k):
        raise _mcp_client.McpAccessDenied("no key", kind="auth")

    monkeypatch.setattr(_mcp_client, "call_tool", _blocked)
    code, _out, err = _run(capsys, ["ask", "月營收"])
    assert code == _cli.EXIT_AUTH
    assert "not a billing one" in err
    assert "pricing" not in err


def test_an_unreachable_server_is_upstream_not_auth(capsys, monkeypatch):
    def _down(*_a, **_k):
        raise _mcp_client.McpUnavailable("connection refused")

    monkeypatch.setattr(_mcp_client, "call_tool", _down)
    code, _out, _err = _run(capsys, ["ask", "月營收"])
    assert code == _cli.EXIT_UPSTREAM


# ---------------------------------------------------------------------------
# 傳輸層
# ---------------------------------------------------------------------------

def test_sse_framing_is_stripped():
    payload = 'data: {"jsonrpc":"2.0","id":1,"result":{"structuredContent":{"rows":[]}}}'
    assert _mcp_client._decode(payload)["result"]["structuredContent"] == {"rows": []}


def test_structured_content_wins_over_the_text_block():
    """⚠️ 只讀 content 的文字會拿到一段給人看的字串,而 CLI 要的是能排表格的結構。"""
    result = {"structuredContent": {"rows": [{"a": 1}]},
              "content": [{"type": "text", "text": "some prose"}]}
    assert _mcp_client._unwrap(result) == {"rows": [{"a": 1}]}


def test_a_json_text_block_is_parsed_when_there_is_no_structured_content():
    result = {"content": [{"type": "text", "text": '{"rows":[{"a":1}]}'}]}
    assert _mcp_client._unwrap(result) == {"rows": [{"a": 1}]}


def test_plain_prose_survives_as_text():
    result = {"content": [{"type": "text", "text": "not json"}]}
    assert _mcp_client._unwrap(result) == {"text": "not json"}


def test_the_endpoint_is_overridable_for_testing(monkeypatch):
    monkeypatch.setenv("TWMD_MCP_URL", "https://example.invalid/mcp")
    assert _mcp_client.mcp_url() == "https://example.invalid/mcp"


# ---------------------------------------------------------------------------
# 鐵律:被 pipe 一律純資料
# ---------------------------------------------------------------------------

def test_ask_help_mentions_as_of(capsys):
    with pytest.raises(SystemExit):
        _cli.main(["ask", "--help"])
    assert "as-of" in capsys.readouterr().out


def test_piped_ask_emits_no_ansi(monkeypatch):
    """subprocess 的 stdout 不是 TTY,等同被 pipe。"""
    import os

    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
           "TWMD_MCP_URL": "https://example.invalid/mcp"}
    result = subprocess.run([sys.executable, "-m", "twmd._cli", "ask", "月營收"],
                            capture_output=True, text=True, env=env, timeout=120)
    assert "\x1b[" not in result.stdout
    assert "████" not in result.stdout
    assert io is not None
