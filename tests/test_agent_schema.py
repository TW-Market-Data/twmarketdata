"""A3:`twmd schema` —— 讓 agent 問得到這支 CLI 長什麼樣。

⚠️ 這一批真正要守的不是「有一個 schema 指令」,是**那份 schema 不會和 CLI 漂開**。

一份手寫的 schema 漂掉時,**兩邊都不會變紅**:CLI 照常跑,schema 照常輸出,
只是它描述的是上個月的 CLI。下一個讀它的 agent 會照著過期的說明組指令,
而組出來的指令會以「參數解析出空值」的方式安靜地錯。
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

import pytest

from twmd import agent_contract as C
from twmd import agent_schema as S
from twmd._cli import build_parser

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(args, env=None):
    environment = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    environment.update(env or {})
    return subprocess.run([sys.executable, "-m", "twmd._cli", *args],
                          capture_output=True, text=True, env=environment, timeout=120)


# ---------------------------------------------------------------------------
# ⚠️ 漂移 —— 這一批的主負向對照
# ---------------------------------------------------------------------------

def test_a_new_flag_shows_up_without_anyone_editing_the_schema():
    """**負向對照 —— 這一批存在的理由。**

    ⚠️ 臨時往 parser 塞一個旗標,schema **必須**看得到它。

    看不到,就代表 schema 是另外抄的一份 —— 而抄的那份漂掉時,
    CLI 和 schema 都不會變紅。
    """
    parser = build_parser()
    subparsers = [a for a in parser._actions              # noqa: SLF001
                  if isinstance(a, argparse._SubParsersAction)]  # noqa: SLF001
    subparsers[0].choices["get"].add_argument("--totally-new-flag", help="added at test time")

    schema = S.agent_schema(parser)
    get = next(c for c in schema["commands"] if c["command"] == "get")
    assert any("--totally-new-flag" in (a.get("flags") or []) for a in get["arguments"])


def test_every_real_subcommand_is_in_the_schema():
    """⚠️ 少列一支指令,agent 就永遠不會用它 —— 而輸出看起來完全正常。"""
    parser = build_parser()
    subparsers = [a for a in parser._actions              # noqa: SLF001
                  if isinstance(a, argparse._SubParsersAction)]  # noqa: SLF001
    real = set(subparsers[0].choices)
    described = {c["command"] for c in S.agent_schema(parser)["commands"]}
    assert described == real


def test_the_choices_come_from_the_parser_not_from_a_copy():
    """⚠️ `--format` 的可選值是**會變的**(這批之前才剛加過 parquet)。
    抄一份就等於埋一個會在下次改格式時失效的說明。"""
    schema = S.agent_schema(build_parser())
    datasets = next(c for c in schema["commands"] if c["command"] == "datasets")
    fmt = next(a for a in datasets["arguments"] if "--format" in (a.get("flags") or []))
    parser = build_parser()
    subparsers = [a for a in parser._actions              # noqa: SLF001
                  if isinstance(a, argparse._SubParsersAction)]  # noqa: SLF001
    real = next(a for a in subparsers[0].choices["datasets"]._actions   # noqa: SLF001
                if "--format" in a.option_strings)
    assert fmt["choices"] == list(real.choices)


# ---------------------------------------------------------------------------
# ⚠️ 只講機制,不講保證
# ---------------------------------------------------------------------------

def test_there_is_no_tool_level_point_in_time_boolean():
    """**負向對照。**

    ⚠️ 一個 `"point_in_time_safe": true` 會**蓋掉** per-dataset 的事實。
    PIT 對不對取決於這次呼叫有沒有給 `--as-of`,以及那個資料集的知識時間欄位 ——
    工具層沒有資格回答它。
    """
    blob = json.dumps(S.agent_schema(build_parser()))
    assert "point_in_time_safe" not in blob
    pit = S.agent_schema(build_parser())["point_in_time"]
    assert "--as-of" in pit["mechanism"]
    assert "look-ahead" in pit["omitted_means"]           # 省略的後果要講出來


def test_the_read_only_verdict_is_computed_not_hard_coded():
    """⚠️ 一個寫死的 `read_only: true`,在有人加了寫入指令的那天**不會改變** ——
    而那正是它唯一該改變的那天。

    餵一個不在對應表也不在本機清單裡的指令進去,verdict 必須翻掉。
    """
    fake = [{"command": "delete_everything", "help": "", "arguments": []}]
    verdict = S._read_only_assessment(fake)
    assert verdict["verdict"] == "unclassified_commands_present"
    assert "delete_everything" in verdict["unclassified_commands"]


def test_the_real_cli_comes_out_read_only():
    assert S._read_only_assessment(
        S.agent_schema(build_parser())["commands"])["verdict"] == "read_only"


def test_get_is_classified_through_the_mcp_tool_it_calls():
    """⚠️ `READ_ONLY_TOOLS` 是 **MCP 工具名**,CLI 指令名是另一個命名空間。

    我第一版直接相減,於是 `get`/`ticker` 被報成「未分類」—— 而它們正是這支
    最主要的兩個取資料指令。修法是寫出對應關係,不是把它們塞進豁免清單。
    """
    access = S.agent_schema(build_parser())["access"]
    assert access["cli_to_mcp_tool"]["get"] == "query_dataset"
    assert "get" not in access["unclassified_commands"]


# ---------------------------------------------------------------------------
# 版本軸 / 契約一致
# ---------------------------------------------------------------------------

def test_schema_version_and_contract_version_are_separate_axes():
    """⚠️ schema 的**形狀**和錯誤信封的**契約**各自會變。合成一個版本號,
    等於逼呼叫端用一個數字去分辨兩種東西。"""
    schema = S.agent_schema(build_parser())
    assert schema["schema_version"] == S.SCHEMA_VERSION
    assert schema["contract_version"] == C.CONTRACT_VERSION
    assert "schema_version" in schema and "contract_version" in schema


def test_the_exit_codes_in_the_schema_are_the_real_ones():
    """⚠️ schema 列一份自己的 exit code,等於文件說謊 —— 而讀的人會照著它寫
    `if rc == 4`。"""
    assert S.agent_schema(build_parser())["exit_codes"] == dict(C.EXIT_CODES)


def test_the_schema_says_which_formats_actually_carry_an_error_envelope():
    """⚠️ 一個 agent 若以為 csv 失敗時也有信封可解,它會去 parse 一段**空的** stdout。"""
    schema = S.agent_schema(build_parser())
    assert schema["envelope_formats"] == sorted(C.ENVELOPE_FORMATS)
    assert "csv.reader" in schema["csv_error_note"]


# ---------------------------------------------------------------------------
# CLI 端
# ---------------------------------------------------------------------------

def test_schema_defaults_to_json_because_it_exists_to_be_parsed():
    """⚠️ 這支指令的讀者是程式。預設給人類表格,等於預設給錯的對象。"""
    result = _run(["schema"])
    assert result.returncode == C.EXIT_CODES["ok"]
    json.loads(result.stdout)                       # 不得丟例外


def test_schema_needs_no_api_key():
    """⚠️ 自述是**接上去之前**要讀的東西。要金鑰才能讀,順序就反了。"""
    result = _run(["schema"], env={"TWMD_API_KEY": ""})
    assert result.returncode == C.EXIT_CODES["ok"]
    assert json.loads(result.stdout)["tool"] == "twmd"


def test_the_human_table_is_still_available():
    result = _run(["schema", "--format", "table"])
    assert result.returncode == C.EXIT_CODES["ok"]
    assert "twmd" in result.stdout


def test_schema_output_carries_no_ansi_escapes():
    assert "\x1b[" not in _run(["schema"]).stdout


@pytest.mark.parametrize("key", ["tool", "commands", "exit_codes", "access", "point_in_time",
                                 "discovery", "machine_formats"])
def test_the_top_level_keys_are_stable(key):
    """⚠️ 改鍵名不會讓任何測試變紅,但會讓別人的 parser 靜靜地拿到 None。"""
    assert key in S.agent_schema(build_parser())
