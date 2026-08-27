"""`twmd` —— SDK 的命令列外殼。

## 這是薄殼,不是第二個 client

取數、分頁、PIT 過濾、缺口、錯誤分類**全部**走既有的 `twmd.Client` 與 registry。
⚠️ 一個自己組 HTTP 請求的 CLI 會複製一份 PIT 語意,而兩份 PIT 語意遲早會分歧 ——
分歧的那天,CLI 的回測結果和 SDK 的不一樣,而兩邊看起來都正常。

## 三件不能省的事

1. **省略 `--as-of` 要在 stderr 講一句。** 終端機使用者不會讀 docstring,而
   「拿到的是最新修訂值」正是未來函數進到回測的那條路。
2. **缺口與截斷要印出來。** SDK 用 `warnings` 表達這些(PITDataMissingWarning、
   TruncatedResultWarning …),而 Python 預設**同一個警告只印一次**、
   而且它們不會出現在 stdout 的資料裡。CLI 若不接住,`--format csv` 導進檔案的人
   永遠看不到 —— 而「安靜地少幾列」和完整資料長得一模一樣。
3. **exit code 要分類。** 額度不足 / 權限不足 / 找不到資料集是三種不同的 shell 處置,
   全部回 1 等於逼使用者去 grep 錯誤訊息字串。

## 為什麼不需要 pandas

`Client.dataset()` 在沒有 pandas 時回**純 list of dict**(`frame.to_frame` 的
fallback),而警告照樣發 —— 所以 CLI 兩樣都拿得到,不必把 pandas 變成必裝。
⚠️ 反過來說**不能**用 `raw=True`:那條路在 `_build_meta` 之前就 return 了,
PIT 警告一個都不會發。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import __version__

#: exit code。**分類是重點** —— 讓 shell 有得判,不用 grep 訊息字串。
EXIT_OK = 0
EXIT_ERROR = 1          # 沒歸類到的例外
EXIT_USAGE = 2          # argparse 自己用這個
EXIT_AUTH = 3           # 沒金鑰 / 金鑰無效
EXIT_ENTITLEMENT = 4    # 方案不夠 / 點數不足
EXIT_NOT_FOUND = 5      # 沒有這個資料集
EXIT_RATE_LIMITED = 6   # 被限流
EXIT_VALIDATION = 7     # 參數不合法 / 這個資料集不吃這個參數
EXIT_UPSTREAM = 8       # 我們這端出錯或連不上

_API_KEY_ENV = "TWMD_API_KEY"


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _exit_code_for(exc: BaseException) -> int:
    """把具名例外對映到 exit code。**用既有的例外階層,不自己判字串。**"""
    from . import errors

    # ⚠️ **順序是由窄到寬,而且必須是。**
    # `TierRequiredError` 和 `InsufficientCreditsError` 都**繼承自 `TwmdAuthError`**,
    # 所以把 auth 那條放前面會把它們一起吃掉 —— 於是「沒有金鑰」和「方案不夠 /
    # 點數不足」回同一個 code,而那是兩種完全不同的處置:一個去設環境變數,
    # 一個去升級方案。`DatasetNotFoundError` / `ValidationError` 對
    # `TwmdRequestError` 也是同樣的關係。
    mapping = (
        ((errors.TierRequiredError, errors.InsufficientCreditsError), EXIT_ENTITLEMENT),
        ((errors.MissingApiKeyError, errors.InvalidApiKeyError, errors.TwmdAuthError), EXIT_AUTH),
        ((errors.DatasetNotFoundError,), EXIT_NOT_FOUND),
        ((errors.RateLimitedError,), EXIT_RATE_LIMITED),
        ((errors.UnsupportedParameterError, errors.ValidationError), EXIT_VALIDATION),
        ((errors.TwmdServerError, errors.TwmdRequestError), EXIT_UPSTREAM),
    )
    for types, code in mapping:
        if isinstance(exc, types):
            return code
    return EXIT_ERROR


# --------------------------------------------------------------------------- 輸出

def _write_parquet(rows, meta, *, out: Optional[str], dataset: str = "",
                   columns: Optional[List[str]] = None) -> int:
    """把列寫成 Parquet 檔,**PIT metadata 嵌進 schema**。

    ⚠️ **一定要有 --out。** Parquet 是二進位:寫進 stdout 會弄壞終端機,而且
    管線接收端拿到的是一段沒有長度前綴的位元組流 —— 那不是「不方便」,是壞的。
    所以缺 --out 是 usage error,不是預設寫到某個猜出來的檔名。
    """
    from .agent_contract import EXIT_CODES  # noqa: PLC0415

    if not out:
        _err("error: --format parquet needs --out FILE. Parquet is binary; writing it to stdout "
             "would corrupt a terminal and give a pipe an unframed byte stream.")
        return EXIT_CODES["usage"]
    try:
        from .engines import engine_available, missing_engine_hint, to_arrow  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - engines 是本套件的一部分
        _err(f"error: {exc}")
        return EXIT_CODES["error"]
    if not engine_available("arrow"):
        _err(f"error: {missing_engine_hint('arrow')}")
        return EXIT_CODES["error"]

    import pyarrow.parquet as pq  # noqa: PLC0415

    table = to_arrow(list(rows), meta, columns=columns, dataset=dataset)
    pq.write_table(table, out, compression="zstd")
    # ⚠️ 這一行走 **stderr**:stdout 在機器格式下是資料的位置,而這裡的資料
    # 已經在檔案裡了。把「寫好了」印進 stdout,會讓一個 `> file.txt` 的呼叫端
    # 拿到一句人話而不是空的。
    _err(f"wrote {table.num_rows} rows to {out} (parquet, zstd; point-in-time metadata is in "
         f"the Arrow schema — read it back with pyarrow.parquet.read_table(...).schema.metadata)")
    return EXIT_CODES["ok"]


def _emit(rows: Sequence[Dict[str, Any]], fmt: str, columns: Optional[List[str]] = None,
          *, title: str = "", subtitle: str = "") -> None:
    """把列印出來。

    ⚠️ **機器格式的兩條分支放在最前面,而且在任何呈現判斷之前。**
    json/csv 的位元組不該因為「今天有沒有終端機」而不同 —— 呈現層一旦能影響
    這兩條路,某個人的 pipeline 就會在他改用 `| tee` 的那天壞掉。
    """
    if fmt == "json":
        print(json.dumps(list(rows), ensure_ascii=False, default=str, indent=2))
        return
    if fmt == "parquet":
        # ⚠️ **不會走到這裡。** parquet 由呼叫端在拿到 meta 之後自己處理
        # (見 _write_parquet):它需要 Meta 才能把 PIT 嵌進 schema,而 _emit
        # 拿不到 meta。留這個分支是為了讓「忘了接」變成一個明確的錯誤,
        # 而不是靜靜印出一張表。
        raise RuntimeError(
            "parquet must be written by _write_parquet(), which has the Meta needed to embed "
            "point-in-time metadata into the Arrow schema. Reaching _emit() with fmt=parquet "
            "means a command was wired to parquet without that step.")
    names = list(columns or (list(rows[0].keys()) if rows else []))
    if fmt == "csv":
        import csv  # noqa: PLC0415

        writer = csv.DictWriter(sys.stdout, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return
    if not rows:
        _err("(no rows)")
        return
    # 到這裡才輪到「好看」。彩色表格印得出來就用它,印不出來(沒 TTY / 沒裝 rich /
    # NO_COLOR)就落到下面原本那段純文字 —— 兩條路的**資料**完全一樣。
    from . import _cli_ui  # noqa: PLC0415

    if _cli_ui.print_table(list(rows), names, _cli_ui.detect(fmt=fmt),
                           title=title, subtitle=subtitle):
        return
    widths = {n: max(len(str(n)), *(len(str(r.get(n, ""))) for r in rows)) for n in names}
    print("  ".join(str(n).ljust(widths[n]) for n in names))
    print("  ".join("-" * widths[n] for n in names))
    for row in rows:
        print("  ".join(str(row.get(n, "")).ljust(widths[n]) for n in names))


def _rows_of(result: Any) -> List[Dict[str, Any]]:
    """`Client.dataset()` 有 pandas 時回 DataFrame,沒有時回 list —— 兩種都接。"""
    if hasattr(result, "to_dict") and hasattr(result, "columns"):
        return list(result.to_dict("records"))
    return [dict(r) for r in (result or [])]


# --------------------------------------------------------------------------- 子指令

def _cmd_datasets(args: argparse.Namespace) -> int:
    import twmd

    keys = twmd.datasets()
    free = set(twmd.runnable_without_key())
    rows = []
    for key in keys:
        info = twmd.get(key)
        if args.category and str(info.category or "") != args.category:
            continue
        if args.free_only and key not in free:
            continue
        rows.append({"dataset": key, "name_zh": info.name_zh or "",
                     "category": info.category or "",
                     "tier": twmd.access_tier(key),
                     "key_free": "yes" if key in free else "no"})
    _emit(rows, args.format, ["dataset", "name_zh", "category", "tier", "key_free"])
    _err(f"{len(rows)} datasets. 'key_free=yes' runs without an API key.")
    return EXIT_OK


def _cmd_describe(args: argparse.Namespace) -> int:
    import twmd

    caps = twmd.capabilities(args.dataset)
    if args.format == "json":
        print(json.dumps(caps, ensure_ascii=False, indent=2, default=str))
        return EXIT_OK
    for key, value in caps.items():
        if value in (None, "", [], {}):
            continue
        print(f"{key:<24}{value}")
    # ⚠️ 這一行是這個子指令存在的理由 —— 一個 agent/人在取數**之前**就該知道
    # 這個資料集的 as_of 語意,而不是拿到 200 之後才發現它不是 PIT 安全的。
    print(f"\n{'how to read as_of':<24}{caps.get('as_of_note') or caps.get('as_of') or '(not stated)'}")
    return EXIT_OK


def _cmd_coverage(args: argparse.Namespace) -> int:
    import twmd

    info = twmd.get(args.dataset)
    rows = [{"dataset": args.dataset,
             "coverage_start": info.coverage_min or "(unmeasured)",
             "coverage_end": info.coverage_max or "(unmeasured)",
             "point_in_time_safe": info.point_in_time_safe}]
    _emit(rows, args.format, list(rows[0].keys()))
    # 「沒有這筆資料」和「這段期間我們沒收」是兩件事,而空結果長得一樣。
    _err("An empty query result inside this window means no rows matched; outside it, "
         "it means we do not cover that period.")
    return EXIT_OK


def _cmd_get(args: argparse.Namespace) -> int:
    import twmd

    api_key = args.api_key or os.getenv(_API_KEY_ENV) or None
    # ⚠️ **在取資料之前**檢查 --out。放在 fetch 之後的話,一個忘了 --out 的呼叫
    # 會先花掉一次 API 請求(以及使用者的額度)才告訴他參數不對 ——
    # 而那個請求的結果會被直接丟掉。
    if args.format == "parquet" and not getattr(args, "out", None):
        return _write_parquet([], None, out=None, dataset=args.dataset)
    if not args.as_of:
        # 不是所有資料集都吃 as_of,但**省略它的後果**對每個都一樣。
        _err("warning: --as-of was not given, so rows are the LATEST revision, including values "
             "revised after any date you may be reasoning about. For a backtest that is a "
             "look-ahead leak. Pass --as-of YYYY-MM-DD to pin the knowledge date.")

    client = twmd.Client(api_key)
    try:
        with warnings.catch_warnings(record=True) as caught:
            # ⚠️ "always":Python 預設同一個警告只印一次,而每一列缺口都值得被看到。
            warnings.simplefilter("always")
            result = client.dataset(
                args.dataset, ticker=args.ticker, start=args.start, end=args.end,
                as_of=args.as_of, limit=args.limit)
        rows = _rows_of(result)
        info = twmd.get(args.dataset)
        coverage = " → ".join(x for x in (info.coverage_min, info.coverage_max) if x)
        if args.format == "parquet":
            # ⚠️ 在 _emit 之前分流:parquet 需要 Meta 才能把 PIT 嵌進 schema,
            # 而 _emit 只拿得到列。走錯路的話 metadata 會靜靜不見。
            return _write_parquet(rows, getattr(client, "last_meta", None),
                                  out=getattr(args, "out", None), dataset=args.dataset,
                                  columns=info.columns or None)
        # 標題帶資料集名;涵蓋/as_of/verify 交給下面那一行來源註記,不重複印兩次。
        _emit(rows, args.format, title=f"{args.dataset}  {info.name_zh or ''}".strip())
        from . import _cli_ui  # noqa: PLC0415

        _cli_ui.print_provenance(_cli_ui.detect(fmt=args.format), dataset=args.dataset,
                                 as_of=args.as_of, coverage=coverage,
                                 verify_url="https://api.twmarketdata.com/v2/proof/checkpoints")
        # 警告走 stderr —— 這樣 `twmd get ... --format csv > out.csv` 的資料是乾淨的,
        # 而使用者**仍然看得到**缺口。兩者都不能犧牲。
        for warning in caught:
            _err(f"note: {warning.message}")
        meta = getattr(result, "meta", None)
        if meta is not None and getattr(meta, "as_of_applied", None):
            _err(f"note: as_of applied on '{meta.knowledge_time_field}' "
                 f"({meta.as_of_mode}).")
        _err(f"{len(rows)} rows.")
    finally:
        client.close()
    return EXIT_OK


def _known_commands() -> frozenset[str]:
    """已註冊的子指令名。捷徑判斷要先讓路給它們。"""
    return frozenset({"datasets", "describe", "coverage", "get", "auth", "version",
                      "ask", "ticker", "tui"})


def _looks_like_ticker(token: str) -> bool:
    """`twmd 2330` 的判斷。**只認純數字/數字+字母的台股代號形狀**。

    ⚠️ 刻意窄:把任何不認得的字串都當成股號,會讓一個打錯的子指令
    (`twmd datsets`)變成「查不到這檔股票」,而使用者要找的是他打錯了指令。
    """
    value = str(token or "").strip().upper()
    if not 4 <= len(value) <= 6:
        return False
    # 台股代號是 4–5 碼數字,ETF/特殊股別可再帶**一個**字尾字母:
    #   2330 · 0050 · 00631L(5 碼 + L) · 2731A
    # ⚠️ 第一版寫成「前 4 碼數字 + 其餘皆字母」,對 00631L 就錯了(第 5 碼還是數字)。
    # 改成「拿掉最多一個字尾字母之後,剩下必須全是 4–5 碼數字」。
    body = value[:-1] if value[-1].isalpha() else value
    return 4 <= len(body) <= 5 and body.isdigit()


def _cmd_ticker(args: argparse.Namespace) -> int:
    """`twmd 2330` —— 代號捷徑:行情 + 籌碼摘要 + 下一步。"""
    import twmd  # noqa: PLC0415

    from . import _cli_ui  # noqa: PLC0415

    presentation = _cli_ui.detect(fmt=args.format)
    ticker = str(args.ticker).strip().upper()
    api_key = args.api_key or os.getenv(_API_KEY_ENV) or None
    if not args.as_of:
        _err("warning: --as-of was not given, so rows are the LATEST revision. For a backtest "
             "that is a look-ahead leak.")

    # ⚠️ **機器格式只能吐一份文件。**
    # 第一版對每個資料集各 `_emit` 一次,於是 `--format json` 送出兩個接在一起的
    # JSON 陣列、`--format csv` 送出兩份各自帶表頭的 CSV —— 兩種都**解析不了**,
    # 而那正是這個 CLI 的鐵則要防的事(測試就是這樣抓到的)。
    # 所以機器格式收集完一次輸出;人看的表格才逐段印。
    machine = args.format in ("json", "csv")
    collected: List[Dict[str, Any]] = []

    client = twmd.Client(api_key)
    shown = 0
    try:
        for dataset, label in (("twse_daily_price", "日線"), ("monthly_revenue", "月營收")):
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    result = client.dataset(dataset, ticker=ticker, limit=args.limit,
                                            as_of=args.as_of)
                rows = _rows_of(result)
            except Exception as exc:  # noqa: BLE001
                # ⚠️ 一個資料集拿不到,不該讓整個捷徑失敗 —— 其他的照出,
                # 並**說出**哪一個沒拿到。安靜地少一段,讀起來像那段不存在。
                _err(f"note: {dataset} unavailable ({type(exc).__name__}); "
                     f"the sections below are what could be read.")
                continue
            if not rows:
                continue
            shown += 1
            if machine:
                # 每列標明它來自哪個資料集 —— 合成一份之後,少了這一欄就分不出來。
                collected.extend({"dataset": dataset, **row} for row in rows)
            else:
                _emit(rows, args.format, title=f"{ticker} · {label} · {dataset}")
            for warning in caught:
                _err(f"note: {warning.message}")
    finally:
        client.close()

    if machine and collected:
        columns = list(dict.fromkeys(k for row in collected for k in row))
        _emit(collected, args.format, columns)

    if not shown:
        _err(f"no rows for {ticker}. Free access covers these tickers: "
             f"{', '.join(twmd.free_tier_symbols())}")
        return EXIT_NOT_FOUND
    _cli_ui.hint(f"\n想看什麼?\n"
                 f"  twmd get institutional_flow --ticker {ticker}    # 三大法人籌碼\n"
                 f"  twmd get valuation --ticker {ticker}             # 估值\n"
                 f"  twmd describe monthly_revenue                    # 這個資料集的時間語意\n"
                 f"  twmd ask \"{ticker} 最近的營收趨勢\"", presentation)
    return EXIT_OK


def _cmd_tui(_args: argparse.Namespace) -> int:
    from . import _cli_tui  # noqa: PLC0415

    return _cli_tui.run()


def _cmd_ask(args: argparse.Namespace) -> int:
    """`twmd ask "問句"` —— **路由到既有的 MCP `ask` 工具,不在這裡編推斷邏輯。**

    ⚠️ 答案品質等於既有 `ask` 路由的品質。CLI 這一層只做三件事:把問句送過去、
    把回來的東西排版、**把來源印出來**。在這裡自己寫一套「問句 → 資料集」的猜測,
    會和 MCP 那邊的路由分岔 —— 同一個問題兩個答案,而且沒有人會發現。
    """
    from . import _cli_ui, _mcp_client  # noqa: PLC0415

    presentation = _cli_ui.detect(fmt=args.format)
    api_key = args.api_key or os.getenv(_API_KEY_ENV) or None
    question = " ".join(args.question).strip()
    if not question:
        _err("ask what? e.g. twmd ask \"台積電最近三個月的月營收\"")
        return EXIT_USAGE

    arguments: Dict[str, Any] = {"question": question}
    if args.as_of:
        arguments["as_of"] = args.as_of
    else:
        _err("warning: --as-of was not given, so the answer uses the LATEST revision of every "
             "number in it. For anything you will act on historically, pin the knowledge date.")

    try:
        answer = _mcp_client.call_tool("ask", arguments, api_key=api_key)
    except _mcp_client.McpAccessDenied as exc:
        from . import _cli_help  # noqa: PLC0415

        message, steps = _cli_help.access_message(
            exc.kind, dataset="ask", upgrade_url="https://twmarketdata.com/en/pricing")
        _cli_ui.error(message, presentation)
        if exc.kind == "entitlement":
            # ⚠️ 說清楚這是**方案**問題,而且升級不用重連(≤60 秒生效)。
            _cli_ui.hint("  MCP querying starts at the Pro plan. Upgrade with the same email you "
                         "signed in with — the next call picks it up automatically, within about "
                         "a minute. You do not need to reconnect.", presentation)
        _cli_ui.hint(_cli_help.render_next_steps(steps), presentation)
        return EXIT_ENTITLEMENT if exc.kind == "entitlement" else EXIT_AUTH
    except _mcp_client.McpUnavailable as exc:
        _err(f"error: {exc}")
        return EXIT_UPSTREAM

    rows = answer.get("rows") or answer.get("data") or []
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        _emit(rows, args.format, title=question[:70])
    elif args.format == "json":
        print(json.dumps(answer, ensure_ascii=False, default=str, indent=2))
    else:
        # 沒有表格資料時就把答案本身印出來 —— 而它仍然走 stdout,因為那是使用者要的東西。
        print(str(answer.get("answer") or answer.get("text") or
                  json.dumps(answer, ensure_ascii=False, default=str)))

    # ⚠️ **來源一定印。** 一個沒有來源的答案,和一個編出來的答案在讀者眼裡一樣。
    sources = answer.get("sources") or answer.get("citations") or answer.get("query_ids") or []
    if sources:
        _err("sources:")
        for source in (sources if isinstance(sources, list) else [sources]):
            _err(f"  - {source if isinstance(source, str) else json.dumps(source, ensure_ascii=False)}")
    else:
        _err("note: this answer came back without source ids — treat it as unsourced.")
    return EXIT_OK


def _cmd_auth(args: argparse.Namespace) -> int:
    import twmd

    key = args.api_key or os.getenv(_API_KEY_ENV) or ""
    source = ("--api-key" if args.api_key else (f"${_API_KEY_ENV}" if key else "(none)"))
    # ⚠️ 只講前綴與長度,絕不回顯金鑰 —— `auth status` 是最容易被貼進工單的輸出。
    shown = f"{key[:8]}…({len(key)} chars)" if key else "(not set)"
    print(f"{'api key source':<24}{source}")
    print(f"{'api key':<24}{shown}")
    print(f"{'base url':<24}{twmd.DEFAULT_BASE_URL}")
    print(f"{'key-free datasets':<24}{len(twmd.runnable_without_key())}")
    print(f"{'free-tier tickers':<24}{', '.join(twmd.free_tier_symbols())}")
    if not key:
        _err(f"No API key. Set ${_API_KEY_ENV} or pass --api-key. Key-free datasets and the "
             f"free-tier tickers above still work without one.")
    return EXIT_OK


def _cmd_version(_args: argparse.Namespace) -> int:
    print(__version__)
    return EXIT_OK


# --------------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="twmd",
        description="TWMD (TW Market Data) — Taiwan market data with point-in-time correctness.",
        epilog=("Exit codes: 0 ok, 2 usage, 3 auth, 4 entitlement, 5 unknown dataset, "
                "6 rate limited, 7 invalid parameter, 8 upstream, 1 other."))
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command", required=True)

    def _add(name: str, help_text: str, handler: Callable[[argparse.Namespace], int]):
        sub = subs.add_parser(name, help=help_text, description=help_text)
        sub.set_defaults(handler=handler)
        return sub

    listing = _add("datasets", "List available datasets.", _cmd_datasets)
    listing.add_argument("--category", help="filter by category, e.g. chip / fundamental / price")
    listing.add_argument("--free-only", action="store_true",
                         help="only datasets that work without an API key")
    listing.add_argument("--format", choices=("table", "csv", "json"), default="table")

    describe = _add("describe", "Show a dataset's parameters and its as_of semantics.",
                    _cmd_describe)
    describe.add_argument("dataset")
    describe.add_argument("--format", choices=("table", "json"), default="table")

    coverage = _add("coverage", "Show a dataset's coverage window.", _cmd_coverage)
    coverage.add_argument("dataset")
    coverage.add_argument("--format", choices=("table", "csv", "json"), default="table")

    fetch = _add("get", "Fetch rows from a dataset.", _cmd_get)
    fetch.add_argument("dataset")
    fetch.add_argument("--ticker")
    fetch.add_argument("--start")
    fetch.add_argument("--end")
    fetch.add_argument("--as-of", dest="as_of",
                       help="knowledge cutoff YYYY-MM-DD. Omit and you get the latest revision.")
    fetch.add_argument("--limit", type=int)
    # ⚠️ parquet 只給**真的在取資料**的指令。目錄查詢(datasets/describe/
    # coverage)給了只會多一個沒人用卻要維護的分支。
    fetch.add_argument("--format", choices=("table", "csv", "json", "parquet"),
                       default="table")
    fetch.add_argument("--out", help="parquet 的輸出檔路徑。⚠️ --format parquet 必填 ——\n                       parquet 是二進位,寫進 stdout 會弄壞終端機、也管線不了。")
    fetch.add_argument("--api-key", help=f"overrides ${_API_KEY_ENV}")

    ticker = _add("ticker", "Everything about one ticker (also: `twmd 2330`).", _cmd_ticker)
    ticker.add_argument("ticker")
    ticker.add_argument("--as-of", dest="as_of")
    ticker.add_argument("--limit", type=int, default=5)
    ticker.add_argument("--format", choices=("table", "csv", "json", "parquet"),
                        default="table")
    ticker.add_argument("--out", help="parquet 的輸出檔路徑(--format parquet 必填)")
    ticker.add_argument("--api-key")

    _add("tui", "Full-screen terminal UI (needs the [cli] extra; real terminals only).", _cmd_tui)

    ask = _add("ask", "Ask in plain language; routed to the MCP `ask` tool.", _cmd_ask)
    ask.add_argument("question", nargs="+", help='e.g. twmd ask "台積電最近三個月的月營收"')
    ask.add_argument("--as-of", dest="as_of",
                     help="knowledge cutoff YYYY-MM-DD; omit and you get the latest revision")
    ask.add_argument("--format", choices=("table", "csv", "json"), default="table")
    ask.add_argument("--api-key", help=f"overrides ${_API_KEY_ENV}")

    auth = _add("auth", "Show which API key is in use and what works without one.", _cmd_auth)
    auth.add_argument("--api-key")

    _add("version", "Print the SDK version.", _cmd_version)
    return parser


def _friendly(exc: BaseException, code: int, args: Any) -> bool:
    """把例外翻成「發生什麼事 + 下一步」。回 True 表示已經講完了。

    ⚠️ 只在**真人終端機**上加工。被 pipe 的時候 stderr 也維持素的一行 ——
    有人把 stderr 一起收進日誌,而彩色標記在日誌裡是噪音。
    """
    from . import _cli_help, _cli_ui  # noqa: PLC0415

    presentation = _cli_ui.detect(fmt=getattr(args, "format", None))
    dataset = str(getattr(args, "dataset", "") or "")

    if code == EXIT_NOT_FOUND and dataset:
        import twmd  # noqa: PLC0415

        message, steps = _cli_help.unknown_dataset_message(dataset, twmd.datasets())
    elif code == EXIT_AUTH:
        message, steps = _cli_help.access_message("auth")
    elif code == EXIT_ENTITLEMENT:
        message, steps = _cli_help.access_message(
            "entitlement", dataset=dataset,
            upgrade_url="https://twmarketdata.com/en/pricing")
    else:
        return False

    _cli_ui.error(message, presentation)
    _cli_ui.hint(_cli_help.render_next_steps(steps), presentation)
    return True


def _emit_machine_error(fmt, code: int, exc: BaseException) -> None:
    """機器格式下把錯誤信封印到 **stdout**。人類格式什麼都不做。"""
    from .agent_contract import render_error  # noqa: PLC0415

    payload = render_error(fmt, exit_code=code, message=str(exc))
    if payload is not None:
        print(payload)


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw = list(argv) if argv is not None else list(sys.argv[1:])
    # `twmd 2330` 捷徑:第一個 token 長得像台股代號就當成 `twmd ticker 2330`。
    # ⚠️ 判斷刻意窄(見 `_looks_like_ticker`)—— 把不認得的字串都當股號,會讓
    # 一個打錯的子指令變成「查不到這檔股票」,而使用者要找的是他打錯了指令。
    if raw and _looks_like_ticker(raw[0]) and raw[0] not in _known_commands():
        raw = ["ticker", *raw]
    # 零參數 = 軌 A。⚠️ 只有在**真人終端機**才進互動模式:被 pipe 的無參數呼叫
    # 進了選單就會永遠等一個不會來的輸入,那是掛住,不是介面。
    if not raw:
        from . import _cli_ui  # noqa: PLC0415

        if _cli_ui.detect().banner:
            # 有 textual 就進全 TUI,沒有就退回 Phase 1 的引導選單。
            # ⚠️ 兩條路都只在真人終端機 —— 被 pipe 時上面那個 banner 判斷已經是 False。
            from . import _cli_tui  # noqa: PLC0415

            if _cli_tui.can_start()[0]:
                return _cli_tui.run()
            from . import _cli_interactive  # noqa: PLC0415

            return _cli_interactive.run()
        build_parser().print_help()
        return EXIT_USAGE

    parser = build_parser()
    args = parser.parse_args(raw)
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        _err("interrupted")
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 — 這是最外層;分類之後回對應的 code
        code = _exit_code_for(exc)
        # ⚠️ **機器格式下,失敗也要在 stdout 給一份可解析的東西。**
        #
        # 0.5.0 實測:`twmd get no-such-dataset --format json` 的 stdout 是**空的**,
        # 於是 agent 的 `json.loads(stdout)` 直接炸,唯一的機器訊號只有 exit code,
        # 而「為什麼失敗」只有人看得懂的散文、還在 stderr。
        #
        # 一個只在順利時可解析的介面,不是一個介面。
        #
        # 印在 stdout 而不是 stderr:對 agent 而言,錯誤**就是**這次呼叫的結果。
        # 人類格式一個字都不變(render_error 對非機器格式回 None)。
        _emit_machine_error(getattr(args, "format", None), code, exc)
        if _friendly(exc, code, args):
            return code
        _err(f"error: {exc}")
        if code == EXIT_AUTH:
            _err(f"hint: set ${_API_KEY_ENV}, or run `twmd datasets --free-only` for the "
                 f"datasets that need no key.")
        return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
