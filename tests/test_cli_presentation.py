"""呈現層 —— **鐵律:機器拿到的永遠乾淨。**

這支是先寫的,不是最後補的。理由:banner 和顏色是這批唯一會**污染既有輸出**的
改動,而污染的樣子(色碼混進 CSV)只有在別人的 pipeline 裡才會被發現。
"""

from __future__ import annotations

import io
import json
import subprocess
import sys

import pytest

from twmd import _cli, _cli_ui


class _FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class _FakePipe(io.StringIO):
    def isatty(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# detect() —— 單一判斷點
# ---------------------------------------------------------------------------

def test_a_real_terminal_gets_colour_and_banner():
    seen = _cli_ui.detect(fmt="table", stream=_FakeTTY(), env={})
    if not _cli_ui.rich_available():
        pytest.skip("[cli] extra 沒裝,這條測的是裝了之後的行為")
    assert seen.colour is True and seen.banner is True


@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_machine_formats_never_get_colour(fmt):
    """⚠️ 即使在真終端機。`--format json` 的意思就是「我要餵給程式」。"""
    seen = _cli_ui.detect(fmt=fmt, stream=_FakeTTY(), env={})
    assert seen.colour is False and seen.banner is False
    assert fmt in seen.reason


def test_being_piped_removes_colour_and_banner():
    seen = _cli_ui.detect(fmt="table", stream=_FakePipe(), env={})
    assert seen.colour is False and seen.banner is False
    assert "not a terminal" in seen.reason


def test_no_color_is_honoured_by_presence_not_value():
    """no-color.org 的約定:**有設就算**,值是什麼都不管。

    ⚠️ 檢查值(例如只認 "1")等於發明一個別人不知道的規則,而那個人會以為
    自己已經關掉顏色了。
    """
    for value in ("1", "0", "", "false", "no"):
        seen = _cli_ui.detect(fmt="table", stream=_FakeTTY(), env={"NO_COLOR": value})
        assert seen.colour is False, f"NO_COLOR={value!r} 沒被尊重"


def test_dumb_terminal_gets_no_colour():
    seen = _cli_ui.detect(fmt="table", stream=_FakeTTY(), env={"TERM": "dumb"})
    assert seen.colour is False


def test_an_unaskable_stream_falls_to_plain():
    """負向對照:問不出 isatty 就當作不是終端機 —— **往乾淨的方向錯**。"""
    class _Weird:
        def isatty(self):
            raise OSError("no")

    assert _cli_ui.detect(fmt="table", stream=_Weird(), env={}).colour is False


def test_banner_is_empty_when_not_wanted():
    plain = _cli_ui.Presentation(False, False, "piped")
    assert _cli_ui.render_banner(plain, version="0.4.0", status="x") == ""


# ---------------------------------------------------------------------------
# 端到端:真的跑一次 CLI,檢查 stdout 的位元組
# ---------------------------------------------------------------------------

def _run(args, env=None):
    import os

    environment = {**os.environ, "PYTHONPATH": str(__import__("pathlib").Path(
        __file__).resolve().parents[1])}
    environment.update(env or {})
    return subprocess.run([sys.executable, "-m", "twmd._cli", *args],
                          capture_output=True, text=True, env=environment, timeout=120)


def test_piped_output_carries_no_ansi_escapes():
    """**這是鐵律的驗收條件。** subprocess 的 stdout 不是 TTY,等同被 pipe。"""
    result = _run(["datasets", "--free-only"])
    assert result.returncode == 0, result.stderr
    assert "\x1b[" not in result.stdout, "被 pipe 還吐色碼"
    assert "████" not in result.stdout, "被 pipe 還吐 banner"


def test_piped_csv_is_parseable_csv():
    """色碼混進 CSV 只會在別人的 parser 裡才發現 —— 所以在這裡就解析一次。"""
    import csv

    result = _run(["datasets", "--format", "csv"])
    assert result.returncode == 0, result.stderr
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert rows and "dataset" in rows[0]
    assert all("\x1b" not in "".join(str(v) for v in row.values()) for row in rows)


def test_piped_json_is_parseable_json():
    result = _run(["datasets", "--format", "json"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)          # 多一個位元組都會讓這行炸
    assert isinstance(payload, list) and payload


def test_no_color_env_also_strips_escapes():
    result = _run(["datasets", "--free-only"], env={"NO_COLOR": "1"})
    assert "\x1b[" not in result.stdout


def test_bare_invocation_when_piped_prints_help_and_does_not_hang():
    """⚠️ 零參數 + 被 pipe **絕不能**進互動選單 —— 那會永遠等一個不會來的輸入。

    timeout 就是這條測試的斷言:掛住的話 subprocess.run 會丟 TimeoutExpired。
    """
    result = _run([])
    assert result.returncode == _cli.EXIT_USAGE
    assert "usage:" in result.stdout.lower()
    assert "████" not in result.stdout


def test_stdout_stays_data_only_while_notes_go_to_stderr():
    """資料走 stdout、說明走 stderr —— 兩邊都不能犧牲。"""
    result = _run(["datasets", "--free-only", "--format", "csv"])
    assert "datasets." not in result.stdout        # 那句計數在 stderr
    assert "runs without an API key" in result.stderr
