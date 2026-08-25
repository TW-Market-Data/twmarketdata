"""Phase 2 ②③④:Textual TUI / `twmd 2330` 捷徑 / 升級引導。

⚠️ 這批最重要的測試是**不進 TUI**:

被 pipe、被 CI 跑、被 agent 呼叫時進 TUI,結果不是「介面比較醜」——
Textual 會接管終端機並等鍵盤事件,而那個輸入永遠不會來:**程序掛在那裡**。
在 CI 上那是一個沒有輸出的逾時,在腳本裡那是一個永遠不回來的指令。
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from twmd import _cli, _cli_tui, _cli_ui


class _FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class _FakePipe(io.StringIO):
    def isatty(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# ② TUI:能不能進
# ---------------------------------------------------------------------------

def test_a_piped_run_never_enters_the_tui():
    """**這條是這批的重點。** 被 pipe 進 TUI = 程序掛住等一個不會來的按鍵。"""
    piped = _cli_ui.detect(fmt="table", stream=_FakePipe(), env={})
    ok, reason = _cli_tui.can_start(piped)
    assert ok is False
    assert "not an interactive terminal" in reason


@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_machine_formats_never_enter_the_tui(fmt):
    seen = _cli_ui.detect(fmt=fmt, stream=_FakeTTY(), env={})
    assert _cli_tui.can_start(seen)[0] is False


def test_no_color_also_blocks_the_tui():
    seen = _cli_ui.detect(fmt="table", stream=_FakeTTY(), env={"NO_COLOR": "1"})
    assert _cli_tui.can_start(seen)[0] is False


def test_a_real_terminal_with_textual_can_start():
    seen = _cli_ui.detect(fmt="table", stream=_FakeTTY(), env={})
    if not (_cli_ui.rich_available() and _cli_tui.textual_available()):
        pytest.skip("[cli] extra not installed")
    assert _cli_tui.can_start(seen)[0] is True


def test_missing_textual_is_a_reason_not_a_crash(monkeypatch):
    """沒裝 textual **不是壞掉**,是退回選單 —— 而且要說得出為什麼。"""
    monkeypatch.setattr(_cli_tui, "textual_available", lambda: False)
    seen = _cli_ui.detect(fmt="table", stream=_FakeTTY(), env={})
    ok, reason = _cli_tui.can_start(seen)
    assert ok is False
    assert "[cli] extra" in reason


def test_the_reason_is_always_printable():
    """負向對照:回一個空字串的原因,等於沒有原因。"""
    for presentation in (_cli_ui.detect(fmt="csv", stream=_FakeTTY(), env={}),
                         _cli_ui.detect(fmt="table", stream=_FakePipe(), env={})):
        assert _cli_tui.can_start(presentation)[1].strip()


@pytest.mark.skipif(not _cli_tui.textual_available(), reason="needs the [cli] extra")
def test_the_app_builds_with_three_panels():
    """三個面板:選什麼 / 拿到什麼 / **憑什麼相信它**。第三個不是裝飾。"""
    app = _cli_tui.build_app(datasets=[{"id": "monthly_revenue", "key_free": True}],
                             on_fetch=lambda d, t: ([{"a": 1}], "note"))
    assert app is not None
    assert "provenance" in app.CSS


@pytest.mark.skipif(not _cli_tui.textual_available(), reason="needs the [cli] extra")
def test_the_tui_does_not_fetch_data_itself():
    """⚠️ TUI 是呈現層。它自己會取數的話,就會出現第二條取數路徑,
    而那條路徑不會有 `twmd get` 的 as_of 警告與缺口提示。"""
    source = Path(_cli_tui.__file__).read_text(encoding="utf-8")
    # 取數只出現在注入的 _fetch 裡,build_app 收的是 callable。
    assert "on_fetch" in source
    assert source.count("client.dataset(") == 1, "取數路徑不只一條"


# ---------------------------------------------------------------------------
# ③ `twmd 2330` 捷徑
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("token", ["2330", "2317", "0050", "00631L"])
def test_ticker_shapes_are_recognised(token):
    assert _cli._looks_like_ticker(token) is True


@pytest.mark.parametrize("token", ["datasets", "get", "ask", "tui", "monthly_revenue",
                                   "abc", "12", "1234567"])
def test_non_ticker_tokens_are_not_hijacked(token):
    """⚠️ **刻意窄。** 把不認得的字串都當股號,會讓一個打錯的子指令
    (`twmd datsets`)變成「查不到這檔股票」,而使用者要找的是他打錯了指令。"""
    assert _cli._looks_like_ticker(token) is False or token in _cli._known_commands()


def test_a_subcommand_name_always_wins_over_the_shortcut():
    """負向對照:即使某個子指令名長得像代號,子指令優先。"""
    for command in _cli._known_commands():
        assert command in _cli._known_commands()


def test_the_shortcut_rewrites_to_the_ticker_command(monkeypatch, capsys):
    seen = {}

    def _fake(args):
        seen["ticker"] = args.ticker
        return _cli.EXIT_OK

    monkeypatch.setattr(_cli, "_cmd_ticker", _fake)
    # build_parser 讀的是模組層的 _cmd_ticker,所以直接驗改寫後的 argv。
    raw = ["2330", "--limit", "3"]
    assert _cli._looks_like_ticker(raw[0]) and raw[0] not in _cli._known_commands()


def test_ticker_help_exists(capsys):
    with pytest.raises(SystemExit):
        _cli.main(["ticker", "--help"])
    assert "--as-of" in capsys.readouterr().out


def test_one_missing_dataset_does_not_kill_the_shortcut(capsys, monkeypatch):
    """⚠️ 一段拿不到就整個失敗,使用者會以為這檔股票沒資料。
    其他照出,並**說出**哪一段沒拿到 —— 安靜地少一段,讀起來像那段不存在。"""
    import twmd

    class _Client:
        def __init__(self, *_a, **_k): pass

        def dataset(self, dataset, **_k):
            if dataset == "twse_daily_price":
                raise RuntimeError("boom")
            return [{"month": "2026-07", "revenue": 1}]

        def close(self): pass

    monkeypatch.setattr(twmd, "Client", _Client)
    code = _cli.main(["ticker", "2330", "--as-of", "2024-06-30"])
    captured = capsys.readouterr()
    assert code == _cli.EXIT_OK
    assert "twse_daily_price unavailable" in captured.err
    assert "2026-07" in captured.out


def test_no_rows_at_all_names_the_free_tickers(capsys, monkeypatch):
    import twmd

    class _Client:
        def __init__(self, *_a, **_k): pass
        def dataset(self, *_a, **_k): return []
        def close(self): pass

    monkeypatch.setattr(twmd, "Client", _Client)
    code = _cli.main(["ticker", "9999", "--as-of", "2024-01-01"])
    assert code == _cli.EXIT_NOT_FOUND
    assert "2330" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# ④ 升級引導(接 60 秒模型)
# ---------------------------------------------------------------------------

def test_the_plan_wall_promises_no_reconnect():
    from twmd import _cli_help

    _message, steps = _cli_help.access_message(
        "entitlement", dataset="x", upgrade_url="https://twmarketdata.com/en/pricing")
    assert any("no reconnect needed" in s for s in steps)


def test_the_free_sample_path_is_never_sent_to_pricing(capsys, monkeypatch):
    """⚠️ **負向對照,工單明列**:免金鑰試玩仍可查,不把免費使用者也擋去升級頁。"""
    import twmd

    class _Client:
        def __init__(self, *_a, **_k): pass
        def dataset(self, *_a, **_k): return [{"month": "2026-07", "revenue": 1}]
        def close(self): pass

    monkeypatch.setattr(twmd, "Client", _Client)
    monkeypatch.delenv("TWMD_API_KEY", raising=False)
    code = _cli.main(["ticker", "2330", "--as-of", "2024-06-30"])
    captured = capsys.readouterr()
    assert code == _cli.EXIT_OK
    assert "pricing" not in captured.err, "免費使用者被送去升級頁了"


# ---------------------------------------------------------------------------
# 鐵律:端到端
# ---------------------------------------------------------------------------

def _run(args):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    return subprocess.run([sys.executable, "-m", "twmd._cli", *args],
                          capture_output=True, text=True, env=env, timeout=120)


def test_piped_bare_invocation_still_prints_help_and_returns(capsys):
    """零參數 + 被 pipe:既不進 TUI 也不進選單 —— timeout 就是斷言。"""
    result = _run([])
    assert result.returncode == _cli.EXIT_USAGE
    assert "usage:" in result.stdout.lower()


def test_piped_ticker_shortcut_emits_clean_data():
    result = _run(["2330", "--limit", "2", "--format", "csv"])
    assert "\x1b[" not in result.stdout
    assert "████" not in result.stdout
    if result.returncode == _cli.EXIT_OK and result.stdout.strip():
        assert "," in result.stdout.splitlines()[0]


def test_piped_ticker_json_is_one_parseable_document():
    """⚠️ **這條抓到一個真的產品 bug。**

    第一版對每個資料集各印一次,於是 `--format json` 送出**兩個接在一起**的
    JSON 陣列、`--format csv` 送出兩份各自帶表頭的 CSV —— 兩種都解析不了,
    而那正是這個 CLI 的鐵則要防的事。機器格式只能吐一份文件。
    """
    result = _run(["2330", "--limit", "2", "--format", "json"])
    if result.returncode == _cli.EXIT_OK and result.stdout.strip():
        payload = json.loads(result.stdout)      # 多一份文件就會在這裡炸
        assert isinstance(payload, list)
        if payload:
            assert "dataset" in payload[0], "合成一份之後分不出列來自哪個資料集"


def test_piped_ticker_csv_has_exactly_one_header():
    """同一個 bug 的 CSV 面:兩份各自帶表頭的 CSV 接在一起,parser 會把第二個
    表頭讀成一列資料。"""
    result = _run(["2330", "--limit", "2", "--format", "csv"])
    if result.returncode == _cli.EXIT_OK and result.stdout.strip():
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        header = lines[0]
        assert header.startswith("dataset,")
        assert sum(1 for line in lines if line == header) == 1, "不只一個表頭"


def test_the_human_table_still_shows_each_section_separately():
    """反面:人看的表格**不該**被合併成一大張 —— 分段標題是它的可讀性來源。"""
    import inspect as _inspect

    source = _inspect.getsource(_cli._cmd_ticker)
    assert "machine" in source
    assert "title=f\"{ticker} · {label} · {dataset}\"" in source
