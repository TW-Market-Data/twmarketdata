"""E1/E2:`.to_polars()` / `.to_arrow()` + `--format parquet`。

⚠️ 這一批的核心不是「多了兩個輸出格式」,是**PIT metadata 能不能離開這個行程**。

實測(pandas 2.3.3)的存活狀況 —— 和我原本以為的**不一樣**,所以逐項量過:

    to_parquet -> read_parquet   保留  ✅
    groupby / concat             保留  ✅
    merge                        **掉了** ❌
    另一種語言 / DuckDB 讀同一個檔   看不到 `.attrs`,那是 pandas 專屬的

所以 `to_arrow` 的價值要說精確:PIT 進**schema**,任何讀得懂 Parquet 的工具
都拿得到,而且 merge 不會讓它消失。
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

from twmd import engines as E
from twmd.meta import Meta

ROOT = pathlib.Path(__file__).resolve().parents[1]

polars = pytest.importorskip("polars", reason="E1 的 Polars 路徑沒有它就沒被測到")
pa = pytest.importorskip("pyarrow", reason="E2 的 Parquet 路徑沒有它就沒被測到")
pq = pytest.importorskip("pyarrow.parquet")


def _rows(n=3):
    return [{"ticker": "2330", "trade_date": f"2026-08-{20+i:02d}", "close": 1000 + i}
            for i in range(n)]


def _meta(**kw):
    base = {"dataset": "twse_daily_price", "route": "/v2/datasets/twse-daily-price",
            "row_count": 3, "as_of_requested": "2026-06-30", "as_of_applied": True,
            "as_of_field": "trade_date", "knowledge_time_field": "trade_date"}
    base.update(kw)
    return Meta(**base)


# ---------------------------------------------------------------------------
# ⚠️ 往返:PIT 要能離開這個行程(這一批最重要的一條)
# ---------------------------------------------------------------------------

def test_point_in_time_survives_a_parquet_round_trip(tmp_path):
    """**負向對照 —— 這批存在的理由。**

    ⚠️ 一份不知道自己是哪個時點的資料,和一份知道的,在檔案裡長得一模一樣。
    這一條確認 PIT 真的寫進去、也真的讀得回來。
    """
    table = E.to_arrow(_rows(), _meta(), dataset="twse_daily_price")
    path = tmp_path / "out.parquet"
    pq.write_table(table, path)

    read_back = pq.read_table(path)
    pit = E.decode_pit_metadata(read_back.schema.metadata)
    assert pit["as_of_requested"] == "2026-06-30"
    assert pit["knowledge_time_field"] == "trade_date"
    assert pit["dataset"] == "twse_daily_price"


def test_where_a_pandas_attrs_actually_gets_lost(tmp_path):
    """⚠️ **實測更正:我原本的說法是誇大的。**

    我第一版斷言 pandas 的 `.attrs` 撐不過 parquet 往返 —— **它撐得過**
    (pandas 2.3.3 實測,往返後 attrs 還在)。

    真正會掉的地方是 **merge**:

        往返 to_parquet/read_parquet   保留  ✅
        groupby().sum()                保留  ✅
        concat()                       保留  ✅
        merge()                        **掉了** ❌

    這一條把量到的事實釘住,而不是釘一個聽起來更有力的故事。`to_arrow` 的價值
    因此要說得更精確:它讓 PIT 進入 **schema**,所以任何讀得懂 Parquet 的工具
    (DuckDB / Spark / 另一種語言)都拿得到 —— 而 `.attrs` 只有 pandas 自己看得見。
    """
    pandas = pytest.importorskip("pandas")

    frame = pandas.DataFrame(_rows())
    frame.attrs["as_of"] = "2026-06-30"
    path = tmp_path / "pandas.parquet"
    frame.to_parquet(path)

    # 往返:pandas 自己讀得回來
    assert pandas.read_parquet(path).attrs.get("as_of") == "2026-06-30"

    # ⚠️ 但 merge 之後就沒了 —— 而合併資料集正是回測管線最常做的事。
    merged = frame.merge(pandas.DataFrame([{"ticker": "2330", "sector": "semis"}]),
                         on="ticker")
    assert merged.attrs.get("as_of") is None


def test_arrow_metadata_is_readable_without_pandas(tmp_path):
    """⚠️ 這才是 `to_arrow` 真正多給的東西:PIT 在 **schema** 裡,
    所以任何讀得懂 Parquet 的工具都拿得到 —— `.attrs` 只有 pandas 看得見。"""
    table = E.to_arrow(_rows(), _meta(), dataset="twse_daily_price")
    path = tmp_path / "arrow.parquet"
    pq.write_table(table, path)

    # 不經過 pandas,直接讀 schema
    schema = pq.read_schema(path)
    pit = E.decode_pit_metadata(schema.metadata)
    assert pit["as_of_requested"] == "2026-06-30"


def test_no_pit_facts_means_no_empty_shell(tmp_path):
    """**負向對照。** ⚠️ 一個只有 note 而沒有 as_of 的 metadata,讀的人會以為
    「有帶 PIT」—— 那比完全沒有更糟。"""
    assert E.pit_metadata(None) == {}
    table = E.to_arrow(_rows(), None)
    assert E.decode_pit_metadata(table.schema.metadata) == {}


def test_the_metadata_keys_match_what_meta_actually_has():
    """**負向對照 —— 實測抓到的。**

    ⚠️ 我第一版憑印象寫了 `as_of` / `point_in_time_mode`,而 `Meta` 上叫
    `as_of_requested` / `as_of_mode`。`getattr` 的預設值會讓那些鍵**靜靜消失** ——
    產出的 Parquet 沒有 as_of,而檔案看起來完全正常。
    """
    pit = E.decode_pit_metadata(E.pit_metadata(_meta()))
    assert "as_of_requested" in pit
    assert "as_of" not in pit                      # 那個名字不存在於 Meta


def test_only_facts_go_in_not_judgements():
    """⚠️ 「我們認為這份資料是 PIT 安全的」是**判斷**,而判斷會過期 ——
    但檔案不會跟著更新。"""
    pit = E.decode_pit_metadata(E.pit_metadata(_meta()))
    assert not any("safe" in key for key in pit)


# ---------------------------------------------------------------------------
# E1:三個引擎
# ---------------------------------------------------------------------------

def test_polars_returns_the_frame_and_the_pit_separately():
    """⚠️ **兩個值**,而且不是為了方便:Polars 沒有 attrs,硬塞 PIT 會變成一個
    **假欄位** —— 而假欄位會被聚合、被 join、被寫進輸出。"""
    frame, pit = E.to_polars(_rows(), _meta())
    assert frame.height == 3
    assert "as_of_requested" not in frame.columns          # 沒有變成假欄位
    assert pit["as_of_requested"] == "2026-06-30"


def test_every_engine_returns_the_same_rows():
    """⚠️ 三條路是**同一批列**的轉換。數字不一樣的話,使用者選引擎就等於選答案。"""
    rows = _rows(5)
    frame, _ = E.to_polars(rows, _meta())
    table = E.to_arrow(rows, _meta())
    expected = [r["close"] for r in rows]
    assert frame.height == table.num_rows == len(rows)
    assert frame["close"].to_list() == expected
    assert table.column("close").to_pylist() == expected


def test_an_empty_result_still_carries_the_real_column_names():
    """⚠️ 下游選欄時該像有資料那樣正常地少一欄,而不是炸在一個看不懂的錯誤上。"""
    columns = ["ticker", "trade_date", "close"]
    frame, _ = E.to_polars([], _meta(), columns=columns)
    table = E.to_arrow([], _meta(), columns=columns)
    assert list(frame.columns) == columns
    assert table.column_names == columns


def test_a_missing_engine_says_what_to_do_next(monkeypatch):
    """⚠️ 一句「polars is required」對使用者沒有用 —— 他要的是**下一步**。"""
    hint = E.missing_engine_hint("polars")
    assert "pip install twmarketdata[polars]" in hint
    assert "nothing is lost" in hint               # 換引擎不會少拿到東西


def test_engine_availability_does_not_import_the_whole_package():
    """⚠️ 用 find_spec 而不是 try/import:問「裝了沒」不該有 import 的副作用。"""
    import ast

    src = (ROOT / "twmd" / "engines.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "engine_available")
    calls = {getattr(c.func, "attr", None) for c in ast.walk(func) if isinstance(c, ast.Call)}
    assert "find_spec" in calls


# ---------------------------------------------------------------------------
# E2:CLI 的 --format parquet
# ---------------------------------------------------------------------------

def _run(args, env=None):
    environment = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    environment.update(env or {})
    return subprocess.run([sys.executable, "-m", "twmd._cli", *args],
                          capture_output=True, text=True, env=environment, timeout=120)


def test_parquet_without_out_is_a_usage_error_not_a_stdout_dump():
    """**負向對照(這一批的安全條)。**

    ⚠️ Parquet 是二進位:寫進 stdout 會弄壞終端機,而管線接收端拿到的是一段
    沒有框界的位元組流。那不是「不方便」,是壞的。
    """
    from twmd.agent_contract import EXIT_CODES

    result = _run(["get", "twse-daily-price", "--format", "parquet"])
    assert result.returncode == EXIT_CODES["usage"]
    assert "binary" in result.stderr
    assert result.stdout.strip() == ""


def test_the_out_check_happens_before_any_api_call():
    """⚠️ 檢查放在 fetch 之後的話,一個忘了 --out 的呼叫會**先花掉一次請求**
    (以及使用者的額度)才告訴他參數不對 —— 而那次請求的結果會被直接丟掉。

    以 stderr 判斷:走到 fetch 的話會先看到 as_of 警告。
    """
    result = _run(["get", "twse-daily-price", "--format", "parquet"])
    assert "--as-of was not given" not in result.stderr


def test_parquet_is_offered_only_on_data_commands():
    """⚠️ 目錄查詢(datasets / describe)給 parquet 只會多一個沒人用卻要維護的分支。"""
    assert "invalid choice" in _run(["datasets", "--format", "parquet"]).stderr


def test_emit_refuses_parquet_loudly_rather_than_printing_a_table():
    """**負向對照。** ⚠️ `_emit` 拿不到 Meta,所以它走 parquet 就代表某個指令
    接錯了 —— 讓它明確炸掉,而不是靜靜印出一張表(那樣 PIT 會不見而沒有人知道)。"""
    from twmd import _cli

    with pytest.raises(RuntimeError, match="point-in-time metadata"):
        _cli._emit(_rows(), "parquet")
