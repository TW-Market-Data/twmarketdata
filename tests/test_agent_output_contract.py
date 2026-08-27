"""A1:agent 輸出契約 + 回歸測試。

⚠️ 這一批**大部分不是新行為** —— 0.5.0 已經在做對的事(機器格式走 stdout、
說明走 stderr、被 pipe 不上色、exit code 分類)。問題是那些行為**沒有被宣告過**,
所以下一次重構時沒有人知道它們正被依賴著,改掉不會有人擋。

這裡把它們釘成契約。真正新的只有一件:**機器格式下的失敗**。
"""

from __future__ import annotations

import csv
import io
import json
import os
import pathlib
import subprocess
import sys

import pytest

from twmd import agent_contract as C

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(args, env=None):
    environment = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    environment.update(env or {})
    return subprocess.run([sys.executable, "-m", "twmd._cli", *args],
                          capture_output=True, text=True, env=environment, timeout=120)


# ---------------------------------------------------------------------------
# ⚠️ exit code 是編號,發出去就不能動
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,code", [
    ("ok", 0), ("error", 1), ("usage", 2), ("auth", 3), ("entitlement", 4),
    ("not_found", 5), ("rate_limited", 6), ("validation", 7), ("upstream", 8),
])
def test_the_exit_codes_are_frozen(name, code):
    """**負向對照 —— 這一批最重要的一條。**

    ⚠️ 重新編號**不會讓任何測試變紅**,也不會讓任何人的腳本報錯 ——
    它只會讓別人腳本裡的 `if rc == 4:` 開始指向別的意思。

    所以逐一釘住數值,而不是只釘「這些名字都存在」。
    """
    assert C.EXIT_CODES[name] == code


def test_the_cli_and_the_contract_agree_on_every_code():
    """⚠️ 契約寫一份、CLI 寫一份,兩份遲早會分岔 —— 而分岔的那天不會有人發現。"""
    from twmd import _cli

    for name, code in C.EXIT_CODES.items():
        attr = f"EXIT_{name.upper()}"
        assert getattr(_cli, attr) == code, attr


def test_usage_stays_2_because_argparse_owns_it():
    """argparse 自己用 2。改它等於和 Python 標準庫打架。"""
    assert C.EXIT_CODES["usage"] == 2


def test_exit_name_never_raises_on_an_unknown_code():
    """⚠️ 這支被用在**錯誤路徑**上。在錯誤路徑再丟一個例外,會把原本的錯誤蓋掉。"""
    assert C.exit_name(99) == "unknown"
    assert C.exit_name(0) == "ok"


# ---------------------------------------------------------------------------
# 機器格式的失敗(唯一真正新的行為)
# ---------------------------------------------------------------------------

def test_json_mode_failure_is_parseable_on_stdout():
    """**負向對照(這一批修的 bug)。**

    ⚠️ 0.5.0 實測:`--format json` 失敗時 stdout 是**空的**,於是
    `json.loads(stdout)` 直接炸,唯一的機器訊號只有 exit code。

    一個只在順利時可解析的介面,不是一個介面。
    """
    result = _run(["get", "no-such-dataset", "--format", "json"])
    assert result.returncode == C.EXIT_CODES["not_found"]
    payload = json.loads(result.stdout)          # 不得丟例外
    assert payload["error"]["code"] == "dataset_not_found"
    assert payload["error"]["exit_code"] == C.EXIT_CODES["not_found"]
    assert payload["error"]["exit_name"] == "not_found"


def test_json_mode_success_is_also_parseable():
    """成功與失敗**兩條路**都要能 json.loads —— 只有一條成立不算契約。"""
    result = _run(["datasets", "--free-only", "--format", "json"])
    assert result.returncode == C.EXIT_CODES["ok"]
    assert isinstance(json.loads(result.stdout), list)


def test_csv_mode_failure_leaves_stdout_EMPTY_on_purpose():
    """**負向對照 —— 反方向。**

    ⚠️ CSV 刻意**不給**錯誤信封:一列 CSV 錯誤和一列資料長得一模一樣,
    消費端的 `csv.reader` 沒有任何辦法分辨 —— 那比空的 stdout 危險得多。
    """
    result = _run(["get", "no-such-dataset", "--format", "csv"])
    assert result.returncode == C.EXIT_CODES["not_found"]
    assert result.stdout.strip() == ""
    assert "csv.reader" in C.CSV_ERROR_NOTE


def test_csv_success_is_still_parseable_csv():
    result = _run(["datasets", "--free-only", "--format", "csv"])
    rows = list(csv.reader(io.StringIO(result.stdout)))
    assert len(rows) > 1


def test_the_human_format_gains_nothing_on_stdout():
    """⚠️ 人類格式一個字都不能變 —— 這批是**加**一條機器路徑,不是改既有輸出。"""
    result = _run(["get", "no-such-dataset"])
    assert result.stdout.strip() == ""
    assert result.returncode == C.EXIT_CODES["not_found"]


def test_the_envelope_carries_a_contract_version():
    """⚠️ 沒有版本的契約,破壞性變更時沒有任何訊號。"""
    envelope = C.error_envelope(exit_code=3, message="x")
    assert envelope["contract_version"] == C.CONTRACT_VERSION


def test_error_code_and_exit_code_are_separate_axes():
    """⚠️ exit code 是**粗分類**(shell 用),error code 是**具體原因**(程式用)。
    合成一個,等於逼呼叫端用一個只有 9 個值的軸去分辨幾十種情況。"""
    envelope = C.error_envelope(exit_code=C.EXIT_CODES["entitlement"], message="x")
    assert envelope["error"]["exit_code"] == 4
    assert envelope["error"]["code"] == "plan_does_not_include_this"


def test_render_error_returns_None_for_human_formats_not_empty_string():
    """⚠️ 空字串會被 `if payload:` 當成「沒有東西」而靜靜跳過 ——
    那正是這條契約要修的那個 bug 的形狀。"""
    assert C.render_error(None, exit_code=1, message="x") is None
    assert C.render_error("table", exit_code=1, message="x") is None
    assert C.render_error("json", exit_code=1, message="x") is not None


# ---------------------------------------------------------------------------
# 既有行為的回歸釘(0.5.0 已經對,但沒被宣告過)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_machine_formats_never_carry_ansi_escapes(fmt):
    result = _run(["datasets", "--free-only", "--format", fmt])
    assert "\x1b[" not in result.stdout


def test_no_color_is_honoured_by_presence_not_value():
    """no-color.org:**存在**就算數。檢查值等於發明一個別人不知道的規則。"""
    result = _run(["datasets", "--free-only"], env={"NO_COLOR": ""})
    assert "\x1b[" not in result.stdout


def test_notes_go_to_stderr_so_stdout_stays_data():
    result = _run(["datasets", "--free-only", "--format", "csv"])
    assert "runs without an API key" in result.stderr
    assert "runs without an API key" not in result.stdout


def test_every_declared_machine_format_is_accepted_by_the_cli():
    """⚠️ 契約列了一個 CLI 不吃的格式,等於文件說謊。"""
    from twmd import _cli_ui

    for fmt in C.MACHINE_FORMATS:
        assert fmt in _cli_ui.MACHINE_FORMATS, fmt


def test_the_envelope_formats_are_a_subset_of_the_machine_formats():
    """⚠️ 一個「會吐錯誤信封」但不算機器格式的格式,會在人類輸出裡冒出 JSON。"""
    assert C.ENVELOPE_FORMATS <= C.MACHINE_FORMATS
