"""A2 —— `twmd ask` 的 point-in-time 唯讀護欄。**純函式,不碰網路。**

## 這一層在防什麼

`ask` 把自然語言送給一個會**生成**東西的服務。生成出來的東西有兩種危險,
而它們的失敗方式完全不同:

    執行面   生成的內容被當成程式碼跑掉      -> RCE。CVE-2024-5565(Vanna.AI)
                                               就是這個形狀:提示注入讓 LLM 產出
                                               程式碼,而呼叫端 exec() 了它。
    語意面   生成的答案沒有知識時間軸        -> 前視。不會報錯、不會有人抱怨,
                                               而回測看起來變好了。

⚠️ 第二種在這個產品裡更危險。第一種會炸得很大聲;第二種只是讓答案**看起來更好**。

## 四條護欄

    1. 絕不執行模型產出   這個套件裡不得有 eval / exec / compile / pickle.loads。
                          有測試以 AST 掃整包 —— 不是掃 `ask` 那一支,是整包,
                          因為下一個加進來的功能不會記得這條規矩。
    2. 唯讀              `ask` 只允許 tools/call 到唯讀工具;任何看起來會寫的
                          工具名一律拒絕。
    3. 強制釘 as_of      沒給就**注入解析後的日期**並說出來,而不是讓答案浮動。
    4. 沒有知識欄就拒絕   走既有的 `pit` 模組判定,不另寫一套。

## ⚠️ 第 3 條為什麼是「注入」而不是「拒絕」

拒絕會讓 `twmd ask "台積電營收"` 這種探索式問法直接不能用,而那是這個指令最常
被使用的方式。注入今天的日期則讓答案**可重現**:同一個問句配同一個 as_of,
明天問還是同一個答案。

⚠️ 但注入必須**說出來**。一個被悄悄改寫的請求,和使用者以為自己送出的那個
不是同一個 —— 那正是這個模組其餘部分在防的事,不該由它自己犯。
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

__all__ = [
    "FORBIDDEN_EXECUTION_NAMES", "READ_ONLY_TOOLS", "AskRefused",
    "assert_read_only_tool", "pin_as_of", "knowledge_axis_verdict",
    "guard_ask_arguments", "guard_ask_answer",
]


class AskRefused(RuntimeError):
    """護欄擋下來了。**拒絕,不是降級。**"""

    def __init__(self, reason: str, *, code: str) -> None:
        super().__init__(reason)
        self.code = code


#: 絕不出現在這個套件裡的名字。⚠️ 這是 CVE-2024-5565 的形狀:
#: 提示注入讓模型產出程式碼,呼叫端執行它。防法不是「檢查產出安不安全」——
#: 檢查一段生成程式碼是否安全是一個沒有正解的問題 —— 而是**從不執行它**。
FORBIDDEN_EXECUTION_NAMES = frozenset({
    "eval", "exec", "compile", "__import__",
})

#: `ask` 允許呼叫的工具。⚠️ 白名單而不是黑名單:黑名單要預測下一個危險的名字,
#: 而白名單只要求「新工具要被明確加進來」。
READ_ONLY_TOOLS = frozenset({"ask", "query_dataset", "describe_dataset", "list_datasets",
                             "find_related", "search_filings", "query_regime"})

#: 工具名看起來會改變狀態的字眼。用在**錯誤訊息**上,讓拒絕說得出理由。
_WRITE_SHAPED = re.compile(r"(write|insert|update|delete|drop|create|set_|mutate|execute)",
                           re.IGNORECASE)


def assert_read_only_tool(tool: str) -> None:
    """`ask` 這條路只准打唯讀工具。

    ⚠️ 白名單。一個模型如果被誘導去要求呼叫別的工具,擋它的是「不在名單上」,
    而不是「名字看起來危險」—— 後者只擋得住你想像得到的名字。
    """
    name = str(tool or "").strip()
    if name in READ_ONLY_TOOLS:
        return
    shaped = _WRITE_SHAPED.search(name)
    raise AskRefused(
        f"ask refused to call {name!r}: it is not on the read-only allowlist"
        + (f" and its name looks state-changing ({shaped.group(0)})" if shaped else "")
        + ". This path answers questions; it never changes anything.",
        code="tool_not_read_only")


def pin_as_of(supplied: Optional[str], *, today: Optional[_dt.date] = None) -> Tuple[str, bool]:
    """回 `(as_of, injected)`。沒給就**釘今天**,而且回報「是注入的」。

    ⚠️ 不拒絕:拒絕會讓探索式問法不能用,而那是 `ask` 最常見的用法。
    ⚠️ 但注入要說出來 —— 一個被悄悄改寫的請求,和使用者以為送出的那個不是同一個。
    """
    text = str(supplied or "").strip()
    if text:
        try:
            _dt.date.fromisoformat(text[:10])
        except ValueError as exc:
            raise AskRefused(
                f"as_of={supplied!r} is not an ISO date (YYYY-MM-DD). Refusing rather than "
                f"guessing: a misparsed knowledge date silently answers a different question.",
                code="as_of_unparseable") from exc
        return text[:10], False
    return (today or _dt.date.today()).isoformat(), True


def knowledge_axis_verdict(info: Any) -> Tuple[bool, str]:
    """這個資料集有沒有可用的知識時間軸。**走既有的 `pit` 模組,不另寫一套。**

    回 `(ok, reason)`。⚠️ 判定邏輯留在 `pit` 那邊是刻意的:CLI 這一層再寫一份,
    就會出現「client 說可以、pit 說不行」的兩個答案,而沒有人會發現。
    """
    from . import pit  # noqa: PLC0415

    try:
        mode = pit.resolve_mode(info, None)
    except pit.PointInTimeUnavailable as exc:
        # ⚠️ `resolve_mode` **丟例外**而不是回 "unsupported",而它的訊息裡有
        # 這個資料集**為什麼**沒有知識軸。吞掉它換成一句自己的話,等於把
        # pit 模組花力氣寫的解釋丟掉,然後在 CLI 這層重新猜一個。
        return False, f"no knowledge-time axis: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"could not resolve a point-in-time mode: {type(exc).__name__}"
    return True, mode


def guard_ask_arguments(arguments: Mapping[str, Any], *,
                        tool: str = "ask",
                        today: Optional[_dt.date] = None) -> Dict[str, Any]:
    """送出**之前**的護欄。回一份補好 as_of 的 arguments。"""
    assert_read_only_tool(tool)
    out = dict(arguments)
    as_of, injected = pin_as_of(out.get("as_of"), today=today)
    out["as_of"] = as_of
    out["_as_of_injected"] = injected
    return out


def guard_ask_answer(answer: Mapping[str, Any], *,
                     dataset_lookup=None) -> Dict[str, Any]:
    """收到答案**之後**的護欄。

    ⚠️ 這一半不能省。送出前釘了 as_of,不代表回來的東西真的是 point-in-time 的:
    模型可能回一個**沒有知識軸**的資料集。那種答案讀起來和有的完全一樣。
    """
    datasets = answer.get("datasets") or answer.get("dataset") or []
    if isinstance(datasets, str):
        datasets = [datasets]

    refusals: list[str] = []
    checked: list[str] = []
    for name in datasets:
        checked.append(str(name))
        if dataset_lookup is None:
            continue
        try:
            info = dataset_lookup(str(name))
        except Exception:  # noqa: BLE001
            # 查不到就**說查不到**,不當成通過。
            refusals.append(f"{name}: not in the registry, so its knowledge axis is unknown")
            continue
        ok, reason = knowledge_axis_verdict(info)
        if not ok:
            refusals.append(f"{name}: {reason}")

    return {
        "datasets_checked": checked,
        "refusals": refusals,
        "point_in_time": not refusals and bool(checked),
        # ⚠️ 沒有資料集名稱時 **不宣稱** PIT。空集合不是通過。
        "note": ("no dataset was named in the answer, so no point-in-time claim is made about it"
                 if not checked else
                 ("every dataset named carries a knowledge-time axis" if not refusals
                  else "at least one dataset named has no usable knowledge-time axis")),
    }
