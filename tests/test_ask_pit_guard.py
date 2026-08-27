"""A2:`twmd ask` 的 PIT 唯讀護欄。

⚠️ 兩種危險,失敗方式完全不同:

    執行面   生成內容被當程式碼跑 -> RCE(CVE-2024-5565 / Vanna.AI 的形狀)
    語意面   答案沒有知識時間軸   -> 前視。不報錯、沒人抱怨,而回測**看起來變好了**

第二種在這個產品裡更危險:第一種會炸得很大聲,第二種只是讓答案看起來更好。
"""

from __future__ import annotations

import ast
import datetime as dt
import pathlib

import pytest

from twmd import _ask_guard as G

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "twmd"


# ---------------------------------------------------------------------------
# ① 絕不執行模型產出(CVE-2024-5565 的形狀)
# ---------------------------------------------------------------------------

def test_the_package_never_calls_a_dynamic_execution_primitive():
    """**負向對照 —— 這一批最重要的一條。**

    ⚠️ 掃的是**整個套件**,不是 ask 那一支。下一個加進來的功能不會記得這條規矩,
    而這條規矩的代價是 RCE。

    防法不是「檢查生成的程式碼安不安全」—— 那是一個沒有正解的問題 ——
    而是**從不執行它**。
    """
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None)
                if name in G.FORBIDDEN_EXECUTION_NAMES:
                    offenders.append(f"{path.name}:{node.lineno} {name}()")
    assert not offenders, offenders


def test_the_forbidden_list_names_the_cve_shape():
    for name in ("eval", "exec", "compile"):
        assert name in G.FORBIDDEN_EXECUTION_NAMES


# ---------------------------------------------------------------------------
# ② 唯讀:白名單,不是黑名單
# ---------------------------------------------------------------------------

def test_a_read_only_tool_passes():
    G.assert_read_only_tool("ask")
    G.assert_read_only_tool("query_dataset")


@pytest.mark.parametrize("tool", ["write_rows", "delete_dataset", "execute_sql",
                                  "set_entitlement", "drop_table"])
def test_a_state_changing_tool_is_refused(tool):
    """**負向對照。** 一個被誘導的模型要求呼叫別的工具時,擋它的是白名單。"""
    with pytest.raises(G.AskRefused) as caught:
        G.assert_read_only_tool(tool)
    assert caught.value.code == "tool_not_read_only"


def test_an_unknown_but_harmless_looking_tool_is_still_refused():
    """⚠️ **白名單而不是黑名單**:黑名單要預測下一個危險的名字,
    而白名單只要求「新工具要被明確加進來」。"""
    with pytest.raises(G.AskRefused):
        G.assert_read_only_tool("totally_innocent_helper")


def test_the_refusal_says_why_not_just_that_it_refused():
    with pytest.raises(G.AskRefused) as caught:
        G.assert_read_only_tool("update_rows")
    message = str(caught.value)
    assert "read-only allowlist" in message
    assert "never changes anything" in message


# ---------------------------------------------------------------------------
# ③ 強制釘 as_of —— 注入,而且說出來
# ---------------------------------------------------------------------------

def test_a_supplied_as_of_is_kept_and_not_marked_injected():
    value, injected = G.pin_as_of("2026-06-30")
    assert (value, injected) == ("2026-06-30", False)


def test_a_missing_as_of_is_pinned_to_today_and_marked_injected():
    """⚠️ 不拒絕:拒絕會讓探索式問法不能用,而那是 ask 最常見的用法。
    釘今天讓答案**可重現** —— 同一個問句配同一個 as_of,明天問還是同一個答案。"""
    value, injected = G.pin_as_of(None, today=dt.date(2026, 8, 27))
    assert (value, injected) == ("2026-08-27", True)


def test_the_injection_is_reported_not_silent():
    """**負向對照。** ⚠️ 一個被悄悄改寫的請求,和使用者以為送出的那個不是同一個
    —— 那正是這個模組其餘部分在防的事,不該由它自己犯。"""
    out = G.guard_ask_arguments({"question": "台積電營收"}, today=dt.date(2026, 8, 27))
    assert out["as_of"] == "2026-08-27"
    assert out["_as_of_injected"] is True


def test_an_unparseable_as_of_is_refused_not_guessed():
    """**負向對照。** ⚠️ 一個解錯的知識日,會安靜地回答另一個問題。"""
    with pytest.raises(G.AskRefused) as caught:
        G.pin_as_of("last tuesday")
    assert caught.value.code == "as_of_unparseable"


def test_guarding_arguments_also_checks_the_tool():
    with pytest.raises(G.AskRefused):
        G.guard_ask_arguments({"question": "x"}, tool="delete_everything")


# ---------------------------------------------------------------------------
# ④ 沒有知識欄就拒絕 —— 走既有的 pit 模組
# ---------------------------------------------------------------------------

class _Info:
    """⚠️ 屬性名照 `pit.resolve_mode` **真的會讀的**那幾個 —— 我第一版憑印象寫,
    少了 as_of_mode 和 key,於是三條測試全部撞在 AttributeError 上,
    而那個錯誤看起來像「護欄壞了」,其實是我的假物件不完整。"""

    def __init__(self, *, as_of_mode="server", key="ds", as_of_note=None):
        self.as_of_mode = as_of_mode
        self.key = key
        self.as_of_note = as_of_note


def test_a_dataset_with_no_knowledge_axis_is_refused():
    """**負向對照(工單指定):生成查詢未帶知識欄 → 拒絕。**"""
    ok, reason = G.knowledge_axis_verdict(_Info(as_of_mode="unsupported"))
    assert ok is False
    assert "no knowledge-time axis" in reason


def test_the_verdict_delegates_to_pit_rather_than_reimplementing_it():
    """⚠️ CLI 這層再寫一份判定,就會出現「client 說可以、pit 說不行」的兩個答案,
    而沒有人會發現。以 AST 確認它真的呼叫 pit.resolve_mode。"""
    src = (PACKAGE / "_ask_guard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = {getattr(n.func, "attr", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_mode" in calls


def test_an_answer_naming_no_dataset_does_not_claim_point_in_time():
    """**負向對照。** ⚠️ 空集合不是通過。"""
    out = G.guard_ask_answer({"answer": "..."})
    assert out["point_in_time"] is False
    assert "no point-in-time claim" in out["note"]


def test_a_dataset_missing_from_the_registry_is_not_treated_as_ok():
    """⚠️ 查不到就說查不到 —— 當成通過,等於對一個我們不認識的東西背書。"""
    def lookup(_name):
        raise KeyError("nope")

    out = G.guard_ask_answer({"datasets": ["mystery_set"]}, dataset_lookup=lookup)
    assert out["point_in_time"] is False
    assert any("not in the registry" in r for r in out["refusals"])


def test_a_dataset_with_a_knowledge_axis_passes():
    out = G.guard_ask_answer(
        {"datasets": ["twse_daily_price"]},
        dataset_lookup=lambda _n: _Info(as_of_mode="server"))
    assert out["point_in_time"] is True
    assert out["refusals"] == []


def test_one_bad_dataset_among_several_sinks_the_claim():
    """⚠️ 「其中一個沒有知識軸」不能被其他幾個的存在蓋過去。"""
    def lookup(name):
        if name == "good":
            return _Info(as_of_mode="server", key="good")
        return _Info(as_of_mode="unsupported", key="bad")

    out = G.guard_ask_answer({"datasets": ["good", "bad"]}, dataset_lookup=lookup)
    assert out["point_in_time"] is False
    assert len(out["refusals"]) == 1
