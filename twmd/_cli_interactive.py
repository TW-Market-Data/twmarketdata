"""軌 A —— 零參數的引導模式。

`twmd` 不帶參數 → banner → 挑分類 → 挑資料集 → 挑股票/區間 → 彩色結果 +
「這筆怎麼來的」+ 下一步。**全程不用打任何 flag。**

## ⚠️ 只在真人終端機

被 pipe 的無參數呼叫進了選單,會永遠等一個不會來的輸入 —— 那是掛住,不是介面。
所以進入點在 `_cli.main` 就先問過 `detect().banner`,這個模組假設自己是被
一個有 TTY 的人叫起來的。

## questionary 沒裝也要能走

`[cli]` extra 才有 questionary。沒有它就退回 `input()` 的編號選單 —— 醜一點,
但一個因為缺 UI 套件就走不完的引導流程,對它要服務的那個人來說等於不存在。
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from . import _cli_ui

_EXIT_OK = 0
_EXIT_ERROR = 1

#: 引導時先問的分類。⚠️ 這是**呈現順序**,不是資料;實際有哪些分類仍由
#: registry 決定,這裡只挑「先問哪幾個」並把其餘歸到「其他」。
_CATEGORY_ORDER = ("price", "fundamental", "chip", "relation", "reference")
_CATEGORY_LABELS = {
    "price": "行情 / 價格",
    "fundamental": "基本面 / 財報",
    "chip": "籌碼 / 法人",
    "relation": "關聯 / 產業鏈",
    "reference": "參考主檔",
}


def _choose(prompt: str, options: Sequence[tuple[str, str]]) -> Optional[str]:
    """選一個。回選中的 value,取消回 None。"""
    if not options:
        return None
    if _cli_ui.questionary_available():
        import questionary  # noqa: PLC0415

        answer = questionary.select(
            prompt, choices=[questionary.Choice(title=label, value=value)
                             for value, label in options]).ask()
        return answer

    # 退路:編號選單。功能一樣,只是不能用方向鍵。
    print(f"\n{prompt}")
    for index, (_value, label) in enumerate(options, 1):
        print(f"  {index}. {label}")
    try:
        raw = input("  選一個編號(直接 Enter 取消):").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not raw.isdigit() or not 1 <= int(raw) <= len(options):
        return None
    return options[int(raw) - 1][0]


def _ask(prompt: str, default: str = "") -> Optional[str]:
    if _cli_ui.questionary_available():
        import questionary  # noqa: PLC0415

        return questionary.text(prompt, default=default).ask()
    try:
        raw = input(f"{prompt} ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return raw or default


def _status_line() -> str:
    """底部狀態列:免金鑰 or 已登入。**不回顯金鑰。**"""
    import os

    import twmd

    key = os.getenv("TWMD_API_KEY", "").strip()
    if key:
        return f"key set ({key[:8]}…) · {len(twmd.datasets())} datasets"
    return (f"no key · {len(twmd.runnable_without_key())} datasets free · "
            f"samples {', '.join(twmd.free_tier_symbols()[:3])}…")


def _categories(catalog: dict[str, Any]) -> list[tuple[str, str]]:
    present = {str(info.category or "") for info in catalog.values()}
    ordered = [(c, _CATEGORY_LABELS.get(c, c)) for c in _CATEGORY_ORDER if c in present]
    others = sorted(present - set(_CATEGORY_ORDER) - {""})
    ordered.extend((c, c) for c in others)
    return ordered


def run() -> int:
    """走一輪引導。回 exit code。"""
    import twmd

    presentation = _cli_ui.detect()
    _cli_ui.print_banner(presentation, version=twmd.__version__, status=_status_line())

    catalog = {key: twmd.get(key) for key in twmd.datasets()}
    free = set(twmd.runnable_without_key())

    category = _choose("想看哪一類?", _categories(catalog))
    if not category:
        _cli_ui.hint("（取消）試試 `twmd datasets` 看完整清單。", presentation)
        return _EXIT_OK

    # 免金鑰的排前面 —— 一個沒有金鑰的人選到需要金鑰的資料集,只會撞牆。
    in_category = [k for k, info in catalog.items() if str(info.category or "") == category]
    options = sorted(in_category, key=lambda k: (k not in free, k))
    dataset = _choose("挑一個資料集:",
                      [(k, f"{k}  {catalog[k].name_zh or ''}"
                           f"{'' if k in free else '  (需要金鑰)'}") for k in options])
    if not dataset:
        return _EXIT_OK

    info = catalog[dataset]
    ticker = ""
    if info.entity_is_stock_ticker:
        samples = twmd.free_tier_symbols()
        ticker = _ask(f"股號?(免金鑰可用:{', '.join(samples)})", default=samples[0]) or ""

    from ._cli import _cmd_get  # noqa: PLC0415

    class _Args:
        pass

    args = _Args()
    args.dataset, args.ticker = dataset, (ticker or None)
    args.start = args.end = args.as_of = args.api_key = None
    args.limit, args.format = 10, "table"

    try:
        _cmd_get(args)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 — 引導模式不該用 traceback 招呼新手
        from . import _cli_help
        from ._cli import _exit_code_for

        code = _exit_code_for(exc)
        kind = {3: "auth", 4: "entitlement"}.get(code)
        if kind:
            message, steps = _cli_help.access_message(
                kind, dataset=dataset, upgrade_url="https://twmarketdata.com/en/pricing")
            _cli_ui.error(message, presentation)
            _cli_ui.hint(_cli_help.render_next_steps(steps), presentation)
        else:
            _cli_ui.error(f"{exc}", presentation)
        return code

    _cli_ui.hint("\n下一步:", presentation)
    _cli_ui.hint(f"  twmd get {dataset} --ticker {ticker or '2330'} --as-of 2024-06-30\n"
                 f"  twmd describe {dataset}      # 這個資料集的時間語意\n"
                 f"  twmd                          # 再走一次", presentation)
    return _EXIT_OK
