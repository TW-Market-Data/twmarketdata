"""友善錯誤與彩色表格 —— 好看的那一半,以及它不該做的事。"""

from __future__ import annotations

import pytest

from twmd import _cli_help, _cli_ui


# ---------------------------------------------------------------------------
# 猜測
# ---------------------------------------------------------------------------

def test_the_dash_form_resolves_to_the_underscore_dataset():
    """⚠️ 這是這支 CLI 最常見的一種打錯:REST 用 dash,SDK 用 underscore。"""
    assert _cli_help.suggest("monthly-revenue", ["monthly_revenue", "twse_daily_price"]) == \
        ["monthly_revenue"]


def test_a_typo_still_finds_the_dataset():
    assert "monthly_revenue" in _cli_help.suggest("monthy_revenue",
                                                  ["monthly_revenue", "balance_sheet"])


def test_nothing_close_gets_no_guess():
    """負向對照:對每個輸入都硬湊一個建議,會在真的打錯時把人帶去別的地方。"""
    assert _cli_help.suggest("zzzzzzzzzz", ["monthly_revenue", "balance_sheet"]) == []


def test_the_message_names_the_guess_and_a_next_step():
    message, steps = _cli_help.unknown_dataset_message("monthly-revenue", ["monthly_revenue"])
    assert "monthly_revenue" in message
    assert any("twmd describe monthly_revenue" in s for s in steps)


def test_with_no_guess_it_still_gives_somewhere_to_go():
    message, steps = _cli_help.unknown_dataset_message("zzzz", ["monthly_revenue"])
    assert "No dataset called" in message
    assert any("twmd datasets" in s for s in steps)


# ---------------------------------------------------------------------------
# 沒金鑰 vs 方案不夠 —— 兩件事
# ---------------------------------------------------------------------------

def test_missing_key_is_described_as_configuration_not_billing():
    message, steps = _cli_help.access_message("auth")
    assert "not a billing one" in message
    assert any("TWMD_API_KEY" in s for s in steps)
    assert not any("pricing" in s for s in steps), "沒金鑰不該把人送去付費頁"


def test_insufficient_plan_says_the_key_is_fine_and_links_upgrade():
    """⚠️ 講成同一句「access denied」,會讓已付費的人反覆檢查金鑰。"""
    message, steps = _cli_help.access_message(
        "entitlement", dataset="balance_sheet", upgrade_url="https://twmarketdata.com/en/pricing")
    assert "key is fine" in message
    assert any("pricing" in s for s in steps)
    assert any("no reconnect needed" in s for s in steps), "升級免重連是這條漏斗的重點"


def test_both_paths_offer_something_that_works_right_now():
    """每一種擋下都要附一行**現在就跑得動**的指令 —— 不然讀完只能離開。"""
    for kind in ("auth", "entitlement"):
        _message, steps = _cli_help.access_message(kind, dataset="x", upgrade_url="u")
        assert any("twmd " in s for s in steps)


# ---------------------------------------------------------------------------
# 表格
# ---------------------------------------------------------------------------

def test_negative_is_red_and_positive_is_green():
    assert _cli_ui._sign_style(-3.2) == _cli_ui.STYLE_NEGATIVE
    assert _cli_ui._sign_style("15.4") == _cli_ui.STYLE_POSITIVE


def test_zero_has_no_colour():
    """零不是好消息也不是壞消息。"""
    assert _cli_ui._sign_style(0) is None


def test_non_numbers_have_no_colour():
    assert _cli_ui._sign_style("2330") == _cli_ui.STYLE_POSITIVE  # 數字就是數字
    assert _cli_ui._sign_style("台積電") is None
    assert _cli_ui._sign_style(True) is None, "布林不是數量"


def test_only_signed_columns_are_coloured():
    """⚠️ 白名單,不是「所有數字都上色」。

    把股價或成交量塗綠沒有意義(它們永遠是正的),只會把真正有意義的漲跌顏色
    稀釋掉 —— 全部都有顏色等於都沒有顏色。
    """
    assert _cli_ui._is_signed_column("yoy") is True
    assert _cli_ui._is_signed_column("漲跌") is True
    assert _cli_ui._is_signed_column("close") is False
    assert _cli_ui._is_signed_column("revenue") is False


def test_a_wide_table_trims_columns_but_says_how_many():
    """⚠️ **少顯示幾欄可以,不說就不行。**

    13 欄擠進 80 字元會讓每格被折成 3 個字,那份輸出比純文字更難讀 ——
    顏色救不了一張讀不了的表。但一張安靜地少了六欄的表,讀起來就是完整的那一張。
    """
    rows = [{f"c{i}": i for i in range(13)}]
    shown, total = _cli_ui._fit_columns(rows, [f"c{i}" for i in range(13)])
    assert total == 13
    assert len(shown) == _cli_ui._MAX_TABLE_COLUMNS < 13


def test_trimming_prefers_columns_that_actually_have_values():
    """整欄皆空的先丟 —— 它們佔寬度卻不帶資訊。"""
    rows = [{"a": 1, "empty": None, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7, "h": 8}]
    shown, _total = _cli_ui._fit_columns(rows, list(rows[0].keys()))
    assert "empty" not in shown


def test_narrow_tables_are_not_trimmed():
    """負向對照:欄數本來就放得下時,一欄都不能少。"""
    rows = [{"a": 1, "b": 2}]
    shown, total = _cli_ui._fit_columns(rows, ["a", "b"])
    assert shown == ["a", "b"] and total == 2


def test_the_table_refuses_to_render_in_plain_mode():
    """呈現層要能**說自己沒印**,呼叫方才知道要走純文字那條。"""
    plain = _cli_ui.Presentation(False, False, "piped")
    assert _cli_ui.print_table([{"a": 1}], ["a"], plain) is False


def test_provenance_says_latest_revision_when_as_of_is_absent(capsys):
    """⚠️ 留白讀起來像「這問題不適用」,而它其實是「你拿到的可能不是當時的數字」。"""
    if not _cli_ui.rich_available():
        pytest.skip("需要 [cli] extra")
    _cli_ui.print_provenance(_cli_ui.Presentation(True, True, "tty"),
                             dataset="monthly_revenue", as_of=None)
    assert "latest revision" in capsys.readouterr().out


def test_markup_is_stripped_in_plain_mode(capsys):
    """純文字模式不該看到 `[bold]` 這種標記殘骸。"""
    _cli_ui.error("[bold]No API key.[/bold] fix it", _cli_ui.Presentation(False, False, "piped"))
    captured = capsys.readouterr()
    assert "[bold]" not in captured.err
    assert "No API key." in captured.err
