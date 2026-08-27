"""E1 —— `.to_polars()` / `.to_arrow()`。**轉換而已,不重取資料。**

## 這個模組不重造既有的東西

`frame.TwmdFrame`(pandas 子類別)和 `Meta` 已經在了,`client.dataset()` 也已經
回它。⚠️ 名字也刻意避開 `twmd/frames.py` —— 那是 0.1.0 的相容 shim,
還有人的程式碼在 import 它。

這裡加的是**另外兩個引擎**,以及一件既有那條路做不到的事:

    把 point-in-time metadata **嵌進 Arrow schema**,讓它跟著資料離開這個行程。

## ⚠️ 為什麼 metadata 要進 schema,而不是只留在 `df.attrs`

實測(pandas 2.3.3),`.attrs` 的存活狀況**不是**「一寫檔就沒了」:

    to_parquet -> read_parquet   保留  ✅
    groupby().sum()              保留  ✅
    concat()                     保留  ✅
    merge()                      **掉了** ❌

⚠️ 我第一版把它寫成「撐不過往返」—— 那是誇大,已更正。真正的兩個理由是:

1. **merge 會掉**,而合併資料集正是回測管線最常做的事。掉了之後,那份
   DataFrame 和一份沒有 as_of 的**看起來一模一樣**,使用者不會收到任何訊號。
2. **`.attrs` 只有 pandas 看得見。** Arrow schema metadata 是**檔案格式的
   一部分**,DuckDB / Spark / 另一種語言讀同一個檔都拿得到。

所以 `to_arrow()` 的價值是「PIT 跟著**檔案**走」,不是「只有它撐得過寫檔」。

## 三個引擎的取捨,寫出來而不是讓人自己踩

    to_df()      pandas。最通用,而 metadata 在 merge/groupby 後**可能消失**
    to_polars()  Polars。快、省記憶體;⚠️ Polars 的 DataFrame **沒有** attrs 這種
                 使用者層 metadata 掛載點,所以 PIT 只能另外回,不能附在物件上
    to_arrow()   pyarrow.Table。⚠️ **唯一**能把 PIT 寫進檔案的一條
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .meta import Meta

__all__ = [
    "PIT_METADATA_PREFIX", "ENGINES", "engine_available", "missing_engine_hint",
    "pit_metadata", "decode_pit_metadata", "to_polars", "to_arrow",
]

#: Arrow schema metadata 的 key 前綴。加前綴才不會撞到使用者自己塞的東西。
PIT_METADATA_PREFIX = "twmd."

#: 支援的引擎 -> 它需要的套件。
ENGINES: Dict[str, str] = {
    "pandas": "pandas",
    "polars": "polars",
    "arrow": "pyarrow",
}


def engine_available(engine: str) -> bool:
    """這個引擎裝了沒。**不 import 整包**,只問得到不得到。"""
    import importlib.util  # noqa: PLC0415

    module = ENGINES.get(str(engine or "").lower())
    if not module:
        return False
    return importlib.util.find_spec(module) is not None


def missing_engine_hint(engine: str) -> str:
    """裝不到時要說的話。

    ⚠️ 一句「polars is required」對使用者沒有用 —— 他要的是**下一步**。
    所以直接給指令;而且順帶說清楚「換引擎不會少拿到東西」,因為三條路都是
    **同一批列**的轉換 —— 不講的話,一個裝不了 polars 的人會以為他被擋在門外。
    """
    module = ENGINES.get(str(engine or "").lower(), str(engine))
    return (f"{module} is not installed. Install it with "
            f"`pip install twmarketdata[{str(engine).lower()}]`, or take the rows raw — "
            f"every engine here is a CONVERSION of the same rows, so nothing is lost.")


def pit_metadata(meta: Optional[Meta], *, dataset: str = "",
                 extra: Optional[Mapping[str, Any]] = None) -> Dict[bytes, bytes]:
    """要嵌進 Arrow schema 的 point-in-time metadata。**bytes → bytes,那是 Arrow 的規格。**

    ⚠️ 只放**事實**,不放推論。`as_of` 是呼叫端給的,`knowledge_time_field` 是
    registry 宣告的 —— 兩個都指得回來源。一個「我們認為這份資料是 PIT 安全的」
    布林值不會進這裡:那是判斷,而判斷會過期,但檔案不會跟著更新。
    """
    payload: Dict[str, str] = {}
    if dataset:
        payload["dataset"] = str(dataset)
    if meta is not None:
        # ⚠️ 欄名照 `Meta` **真的有的**那幾個 —— 我第一版憑印象寫了
        # `as_of` / `point_in_time_mode`,而 Meta 上叫 `as_of_requested` /
        # `as_of_mode`。getattr 的預設值會讓那些鍵**靜靜消失**:
        # 產出的 Parquet 沒有 as_of,而檔案看起來完全正常。
        for field in ("as_of_requested", "as_of_applied", "as_of_field", "as_of_mode",
                      "knowledge_time_field", "pit_caveat", "dataset", "route",
                      "truncated", "row_count"):
            value = getattr(meta, field, None)
            if value not in (None, ""):
                payload[field] = str(value)
    for key, value in dict(extra or {}).items():
        if value not in (None, ""):
            payload[str(key)] = str(value)
    if not payload:
        # ⚠️ 沒有任何 PIT 事實時**不塞空殼**。一個只有 note 而沒有 as_of 的
        # metadata,讀的人會以為「有帶 PIT」—— 那比完全沒有更糟。
        return {}
    payload.setdefault(
        "note",
        "these keys travel INSIDE the Arrow/Parquet schema, so they survive being written to a "
        "file and read back. A pandas .attrs does not survive merge/groupby.")
    return {f"{PIT_METADATA_PREFIX}{k}".encode("utf-8"): str(v).encode("utf-8")
            for k, v in payload.items()}


def decode_pit_metadata(metadata: Optional[Mapping[bytes, bytes]]) -> Dict[str, str]:
    """把 Arrow schema metadata 讀回人看得懂的 dict(只取我們的前綴)。"""
    out: Dict[str, str] = {}
    for key, value in dict(metadata or {}).items():
        name = key.decode("utf-8", "replace") if isinstance(key, bytes) else str(key)
        if not name.startswith(PIT_METADATA_PREFIX):
            continue
        text = value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
        out[name[len(PIT_METADATA_PREFIX):]] = text
    return out


def to_polars(rows: Sequence[Mapping[str, Any]], meta: Optional[Meta] = None, *,
              columns: Optional[Sequence[str]] = None) -> Tuple[Any, Dict[str, str]]:
    """回 `(polars.DataFrame, pit)`。

    ⚠️ **兩個值**,而且不是為了方便。Polars 的 DataFrame 沒有 `attrs` 這種
    使用者層掛載點 —— 硬塞會變成一個**假欄位**,而假欄位會被聚合、被 join、
    被寫進輸出。所以 PIT 另外回,並在這裡說明它為什麼不在物件上。
    """
    if not engine_available("polars"):
        raise ImportError(missing_engine_hint("polars"))
    import polars as pl  # noqa: PLC0415

    data = [dict(row) for row in rows]
    if data:
        frame = pl.DataFrame(data)
    else:
        # 空結果也要帶**真正的欄名**(和 frame.to_frame 同樣的理由):
        # 下游選欄時該像有資料那樣正常地少一欄,而不是炸在一個看不懂的錯誤上。
        frame = pl.DataFrame({name: [] for name in (columns or [])})
    return frame, decode_pit_metadata(pit_metadata(meta))


def to_arrow(rows: Sequence[Mapping[str, Any]], meta: Optional[Meta] = None, *,
             columns: Optional[Sequence[str]] = None,
             dataset: str = "") -> Any:
    """回 `pyarrow.Table`,**PIT metadata 已經嵌進 schema**。

    ⚠️ 這是三條裡唯一能把 as_of 帶出行程的:寫成 Parquet 再讀回來,metadata 還在。
    pandas 的 `.attrs` 在 `to_parquet` 之後不會在。
    """
    if not engine_available("arrow"):
        raise ImportError(missing_engine_hint("arrow"))
    import pyarrow as pa  # noqa: PLC0415

    data = [dict(row) for row in rows]
    if data:
        table = pa.Table.from_pylist(data)
    else:
        schema = pa.schema([(name, pa.string()) for name in (columns or [])])
        table = pa.Table.from_pylist([], schema=schema)
    embedded = pit_metadata(meta, dataset=dataset)
    if embedded:
        table = table.replace_schema_metadata({**(table.schema.metadata or {}), **embedded})
    return table
