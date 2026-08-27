"""A1 —— `twmd` 對 agent 的**輸出契約**。純資料 + 純函式,不碰網路。

## 這個模組不是新功能

0.5.0 已經在做對的事:`--format json/csv` 走 stdout、說明走 stderr、被 pipe 時
不上色、exit code 分類。**問題是那些行為沒有被宣告過。**

一個要寫自動化的人,只能去讀 CLI 的原始碼推論「我可以依賴什麼」。而沒有被
宣告的行為,下一次重構時沒有人知道它被依賴著 —— 改掉不會有人擋。

所以這裡把已有的行為**寫成契約**,並用回歸測試釘住。

## ⚠️ exit code 是**編號**,而編號一旦發出去就不能動

`EXIT_CODES` 的數字是契約的一部分,和欄位名同級。重新編號不會讓任何測試變紅,
也不會讓任何人的腳本報錯 —— 它只會讓 `if rc == 4:` 這種判斷**開始指向別的意思**。

所以這裡把它們凍結,並有測試逐一釘住數值。

## ⚠️ 機器格式下的錯誤,必須也是機器可讀的

實測(0.5.0):`twmd get no-such-dataset --format json` 的 stdout 是**空的**,
exit code 5,而 stderr 印的是一句和錯誤無關的 as_of 警告。

於是 agent 在 `--format json` 下:

    json.loads(stdout)   -> 炸(空字串)
    唯一的機器訊號       -> exit code
    為什麼失敗            -> 只有人看得懂的散文,而且在 stderr

⚠️ 這讓「用 --format json 就能自動化」這句話只在成功路徑上成立。
一個只在順利時可解析的介面,不是一個介面。

契約補上:**機器格式下,失敗也在 stdout 給一個 JSON 錯誤信封**,
而 `json.loads(stdout)` 在成功與失敗兩條路上都成立。
人類格式一個字都不變。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

__all__ = [
    "CONTRACT_VERSION", "EXIT_CODES", "EXIT_NAMES", "MACHINE_FORMATS",
    "ENVELOPE_FORMATS", "CSV_ERROR_NOTE",
    "ERROR_CODES", "error_envelope", "render_error", "exit_name",
]

#: 契約版本。⚠️ 破壞性變更(改編號、改欄位名、改 stdout/stderr 分工)必須升它。
CONTRACT_VERSION = "1"

#: ⚠️ **凍結。** 這些數字是契約的一部分。重新編號不會讓任何測試變紅,
#: 只會讓別人腳本裡的 `if rc == 4:` 開始指向別的意思。
EXIT_CODES: Dict[str, int] = {
    "ok": 0,
    "error": 1,           # 沒歸類到的例外
    "usage": 2,           # argparse 自己用這個,不能改
    "auth": 3,            # 沒金鑰 / 金鑰無效
    "entitlement": 4,     # 方案不夠 / 點數不足
    "not_found": 5,       # 沒有這個資料集
    "rate_limited": 6,
    "validation": 7,      # 參數不合法 / 這個資料集不吃這個參數
    "upstream": 8,        # 我們這端出錯或連不上
}

EXIT_NAMES: Dict[int, str] = {value: key for key, value in EXIT_CODES.items()}

#: 「stdout 是給機器讀的」格式。⚠️ **照 CLI 真正吃的那一組**,不是我希望它吃的那組。
#:
#: 我第一版寫了 `ndjson` —— 而 `_cli.py` 的 `choices` 裡根本沒有它。
#: 一份列了不存在格式的契約,就是文件說謊:讀的人會照著寫 `--format ndjson`,
#: 拿到 argparse 的 usage error,然後懷疑的是自己而不是文件。
#: 有一條測試比對 `_cli_ui.MACHINE_FORMATS`,不讓這兩份再分岔。
MACHINE_FORMATS = frozenset({"json", "csv"})

#: 錯誤信封只給 **JSON**。
#:
#: ⚠️ CSV 刻意排除,而理由不是懶:**一列 CSV 錯誤和一列資料長得一模一樣。**
#: 消費端的 `csv.reader` 會拿到一列看起來像資料的東西,沒有任何辦法分辨那是不是
#: 錯誤 —— 那比空的 stdout 危險得多。
#:
#: 所以 CSV 的失敗訊號是 **exit code + stderr**,而這件事必須寫在契約裡,
#: 不能讓人自己撞到。
ENVELOPE_FORMATS = frozenset({"json"})

#: CSV 為什麼沒有錯誤信封 —— 契約要說得出來。
CSV_ERROR_NOTE = (
    "In --format csv, failures are signalled by the exit code and stderr only; stdout stays "
    "empty. A CSV error row would be indistinguishable from a data row to csv.reader, which is "
    "worse than no output at all.")

#: 穩定的錯誤碼。⚠️ 和 exit code 分開:exit code 是**粗分類**(shell 用),
#: error code 是**具體原因**(程式用)。把兩者合成一個,等於逼呼叫端用一個
#: 只有 9 個值的軸去分辨幾十種情況。
ERROR_CODES: Dict[str, str] = {
    "auth": "missing_or_invalid_api_key",
    "entitlement": "plan_does_not_include_this",
    "not_found": "dataset_not_found",
    "rate_limited": "rate_limited",
    "validation": "invalid_parameter",
    "upstream": "upstream_unavailable",
    "error": "unclassified_error",
    "usage": "usage_error",
}


def exit_name(code: int) -> str:
    """數字 -> 名稱。不認得就回 `unknown`(而不是丟例外)。

    ⚠️ 一個記錄用的查表函式不該有能力讓呼叫端崩潰 —— 它被用在錯誤路徑上,
    而在錯誤路徑上再丟一個例外,會把原本的錯誤蓋掉。
    """
    return EXIT_NAMES.get(int(code), "unknown")


def error_envelope(*, exit_code: int, message: str,
                   code: Optional[str] = None,
                   detail: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """機器格式下的錯誤信封。

    形狀刻意扁平且固定:`error.code` 是 agent 要分支的東西,`error.exit_code`
    讓它對得上 shell 看到的數字。⚠️ 兩個都給,是因為它們在不同的地方被使用,
    而要呼叫端自己從其中一個推另一個,就是在請它重寫這張對照表。
    """
    name = exit_name(exit_code)
    envelope: Dict[str, Any] = {
        "error": {
            "code": code or ERROR_CODES.get(name, "unclassified_error"),
            "message": str(message),
            "exit_code": int(exit_code),
            "exit_name": name,
        },
        "contract_version": CONTRACT_VERSION,
    }
    if detail:
        envelope["error"]["detail"] = dict(detail)
    return envelope


def render_error(fmt: Optional[str], *, exit_code: int, message: str,
                 code: Optional[str] = None,
                 detail: Optional[Mapping[str, Any]] = None) -> Optional[str]:
    """機器格式回一段要印到 **stdout** 的 JSON;人類格式回 `None`。

    ⚠️ 回 `None` 而不是空字串,是為了讓呼叫端只能寫
    `if payload is not None: print(payload)` —— 空字串會被 `if payload:` 當成
    「沒有東西」而靜靜跳過,那正是這條契約要修的那個 bug 的形狀。
    """
    if str(fmt or "").lower() not in ENVELOPE_FORMATS:
        return None
    envelope = error_envelope(exit_code=exit_code, message=message, code=code, detail=detail)
    return json.dumps(envelope, ensure_ascii=False, indent=2)
