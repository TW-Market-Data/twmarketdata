"""A3 —— `twmd schema --json`:讓 agent **問得到**這支 CLI 長什麼樣。

## 這解決的是哪個缺口

`describe` 說的是**一個資料集**;`datasets` 說的是**有哪些資料集**。
沒有任何一支說**這個工具本身**有哪些指令、吃什麼參數、回哪些 exit code。

一個 agent 目前只能用 `--help` 的**人類文字**去猜 —— 而人類文字的排版一改,
猜法就壞了,壞掉的方式還是靜悄悄的(參數解析出空值,不會報錯)。

## ⚠️ 這份 schema **從真的那個 parser 長出來**,不是另外手寫一份

手寫一份 schema 幾乎注定會漂:有人加一個旗標、改一個 choices,
schema 不會跟著動,而**兩邊都不會變紅**。下一個讀它的 agent 會照著一份
過期的說明去組指令。

所以這裡走 `build_parser()` 的 argparse 結構,把參數**讀出來**。
新增一個旗標會自動出現在 schema 裡 —— 有一條測試釘住這件事:
它臨時往 parser 塞一個旗標,然後要求 schema 看得到它。

## ⚠️ 只講「機制」,不講「保證」

這裡**不會**寫 `"point_in_time_safe": true`。PIT 正確與否取決於呼叫端有沒有
給 `--as-of`,以及那個資料集的知識時間欄位是什麼 —— 那是 per-dataset 的事實,
`describe` 已經在回。一個工具層的布林值只會蓋掉它。

同理 `read_only` 是**算出來的**(比對指令名與白名單),不是宣告的。
一個寫死的 `read_only: true`,在有人加了寫入指令的那天不會改變。
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from . import agent_contract as _contract
from ._ask_guard import READ_ONLY_TOOLS

__all__ = ["SCHEMA_VERSION", "command_schema", "agent_schema", "render"]

#: 這份 **schema 形狀**的版本,和 `agent_contract.CONTRACT_VERSION`(錯誤信封的
#: 契約版本)是**兩條不同的軸**。合成一個,等於逼呼叫端用一個版本號去分辨
#: 兩種各自會變的東西。
SCHEMA_VERSION = "1"

#: argparse 的內部 action 類別 -> 呼叫端該知道的形狀。
#: ⚠️ 用 `type(action).__name__` 而不是 isinstance 鏈 —— argparse 的類別是
#: 私有的,而名字在標準庫裡比類別身分穩定。
_ACTION_KINDS = {
    "_StoreTrueAction": "flag",
    "_StoreFalseAction": "flag",
    "_StoreAction": "value",
    "_AppendAction": "value_repeatable",
    "_CountAction": "flag_repeatable",
    "_HelpAction": None,          # --help 不列:每支都有,列了只是雜訊
    "_VersionAction": None,
    "_SubParsersAction": None,
}


def _option_schema(action: argparse.Action) -> Optional[Dict[str, Any]]:
    kind = _ACTION_KINDS.get(type(action).__name__, "value")
    if kind is None:
        return None
    entry: Dict[str, Any] = {"kind": kind, "help": action.help or ""}
    if action.option_strings:
        entry["flags"] = list(action.option_strings)
        entry["name"] = action.dest
        entry["required"] = bool(action.required)
    else:
        # 位置參數。⚠️ `required` 對它的意義和旗標不同,所以用 nargs 表達,
        # 不要把兩種東西塞進同一個布林值。
        entry["name"] = action.dest
        entry["positional"] = True
        entry["required"] = action.nargs not in ("?", "*")
    if action.choices:
        entry["choices"] = list(action.choices)
    if action.default not in (None, False) and kind != "flag":
        entry["default"] = action.default
    if getattr(action, "type", None) is not None:
        entry["type"] = getattr(action.type, "__name__", str(action.type))
    return entry


def command_schema(parser: argparse.ArgumentParser) -> List[Dict[str, Any]]:
    """走 parser 的子指令,把每一支的參數讀出來。

    ⚠️ **讀出來,不是抄一份。** 抄的那份會漂,而漂掉的時候兩邊都不會變紅。
    """
    subparsers = [a for a in parser._actions              # noqa: SLF001 - argparse 沒有公開 API
                  if isinstance(a, argparse._SubParsersAction)]  # noqa: SLF001
    if not subparsers:
        return []
    out: List[Dict[str, Any]] = []
    # `choices` 是 name -> sub-parser;`_choices_actions` 帶著 help 文字。
    helps = {c.dest: (c.help or "") for c in subparsers[0]._choices_actions}  # noqa: SLF001
    for name, sub in subparsers[0].choices.items():
        options = [o for o in (_option_schema(a) for a in sub._actions) if o]  # noqa: SLF001
        out.append({
            "command": name,
            "help": helps.get(name, "") or (sub.description or ""),
            "arguments": options,
        })
    return sorted(out, key=lambda c: c["command"])


def _read_only_assessment(commands: List[Dict[str, Any]]) -> Dict[str, Any]:
    """⚠️ **算出來的,不是宣告的。**

    一個寫死的 `read_only: true`,在有人加了寫入指令的那天**不會改變** ——
    而那正是它唯一該改變的那天。所以比對指令名與唯讀白名單,把對不上的
    列出來,由讀的人自己判斷。
    """
    names = {c["command"] for c in commands}
    # ⚠️ `READ_ONLY_TOOLS` 是 **MCP 工具名**的白名單,和 CLI 指令名是**兩個命名空間**。
    # 第一版直接拿它去減 CLI 指令,於是 get/ticker 被報成「未分類」—— 而它們是
    # 這支最主要的兩個取資料指令。
    #
    # 修法不是把它們塞進 local_only(那是把問題蓋掉),是**寫出對應關係**:
    # 哪個 CLI 指令走哪個 MCP 工具。對應得上,唯讀性就從那個工具繼承下來。
    cli_to_mcp = {"get": "query_dataset", "ticker": "query_dataset", "ask": "ask"}
    # 完全在本機跑、不打 API 的指令(目錄查詢是打包在 _registry.json 裡的)。
    local_only = {"datasets", "describe", "coverage", "schema", "version", "auth", "gaps", "tui"}
    unclassified = sorted(
        name for name in names
        if name not in local_only and cli_to_mcp.get(name, name) not in READ_ONLY_TOOLS)
    return {
        "verdict": "read_only" if not unclassified else "unclassified_commands_present",
        "unclassified_commands": unclassified,
        "cli_to_mcp_tool": cli_to_mcp,
        "note": ("COMPUTED by mapping each CLI command to the MCP tool it calls and checking that "
                 "tool against the read-only allowlist — not asserted. A hard-coded true would not "
                 "change on the day someone adds a writing command, which is the one day it "
                 "should. Commands in unclassified_commands reach neither the map nor the "
                 "local-only set, so nothing here vouches for them."),
    }


def agent_schema(parser: Optional[argparse.ArgumentParser] = None) -> Dict[str, Any]:
    """這支 CLI 的機器可讀自述。"""
    from . import __version__                     # noqa: PLC0415 - 避免 import 迴圈
    from ._cli import build_parser                # noqa: PLC0415

    parser = parser or build_parser()
    commands = command_schema(parser)
    return {
        "tool": "twmd",
        "schema_version": SCHEMA_VERSION,
        # ⚠️ 兩條**不同的軸**:schema 的形狀 vs 錯誤信封的契約。
        "contract_version": _contract.CONTRACT_VERSION,
        "tool_version": __version__,
        "description": parser.description or "",
        "commands": commands,
        "exit_codes": dict(_contract.EXIT_CODES),
        "machine_formats": sorted(_contract.MACHINE_FORMATS),
        "envelope_formats": sorted(_contract.ENVELOPE_FORMATS),
        "error_envelope_note": (
            "only the formats in envelope_formats emit a parseable error object on stdout. "
            "For the others stdout is EMPTY on failure and the exit code is the only machine "
            "signal — see csv_error_note."),
        "csv_error_note": _contract.CSV_ERROR_NOTE,
        "access": _read_only_assessment(commands),
        "point_in_time": {
            "mechanism": "--as-of YYYY-MM-DD on the `get` command",
            "omitted_means": ("the LATEST revision, not the value as it stood at any past date. "
                              "For a backtest that is a look-ahead."),
            "per_dataset_facts": ("`describe <dataset> --format json` carries as_of_mode, "
                                  "knowledge_time_field and the caveat for that dataset."),
            # ⚠️ 這裡**沒有** point_in_time_safe 布林值:對不對取決於呼叫端有沒有給
            # --as-of,以及那個資料集的知識時間欄位 —— 那是 per-dataset 的事實。
            "no_tool_level_guarantee": ("PIT correctness is a property of the CALL, not of this "
                                        "tool. There is deliberately no tool-level boolean here; "
                                        "one would override the per-dataset facts."),
        },
        "discovery": {
            "datasets": "twmd datasets --format json",
            "one_dataset": "twmd describe <dataset> --format json",
            "coverage": "twmd coverage <dataset> --format json",
        },
    }


def render(schema: Dict[str, Any], fmt: str) -> str:
    """把 schema 印成人看的或機器讀的。"""
    import json                                   # noqa: PLC0415

    if fmt == "json":
        return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=False)
    lines = [f"{schema['tool']} {schema['tool_version']}  (schema v{schema['schema_version']})", ""]
    for command in schema["commands"]:
        lines.append(f"  {command['command']:<12}{command['help']}")
        for argument in command["arguments"]:
            flags = " ".join(argument.get("flags") or [f"<{argument['name']}>"])
            suffix = ""
            if argument.get("choices"):
                suffix = f"  ({'|'.join(str(c) for c in argument['choices'])})"
            lines.append(f"      {flags:<26}{argument['help']}{suffix}")
        lines.append("")
    lines.append(f"  access: {schema['access']['verdict']}")
    lines.append(f"  as-of : {schema['point_in_time']['mechanism']}")
    return "\n".join(lines)
