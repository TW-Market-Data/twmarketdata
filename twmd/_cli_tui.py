"""Textual 全 TUI —— 可捲動表格 + 多面板。

## ⚠️ 只在真人終端機,而且這條判斷在最前面

被 pipe、被 CI 跑、被 agent 呼叫時進 TUI,結果不是「介面比較醜」——
Textual 會接管終端機並等鍵盤事件,而那個輸入永遠不會來:**程序就掛在那裡**。
在 CI 上那是一個沒有輸出的逾時,在腳本裡那是一個永遠不回來的指令。

所以進入點問的是 `_cli_ui.detect().banner`(同一個單一判斷點),不是自己再判一次。

## textual 沒裝就退回 Phase 1 的選單

`[cli]` extra 才有 textual。沒有它**不是壞掉** —— 退回既有的引導選單,
那條路已經能完成同樣的事,只是不能捲動。

## 為什麼是三個面板

    左   資料集(可捲動)      —— 選什麼
    右上 結果表(可捲動)      —— 拿到什麼
    右下 來源與 as_of        —— **憑什麼相信它**

第三個面板不是裝飾。一個只顯示數字的終端機介面,會讓使用者忘記那些數字有時點
和來源 —— 而那正是這個產品和一張截圖的差別。
"""

from __future__ import annotations

from typing import Any, Optional

from . import _cli_ui


def textual_available() -> bool:
    try:
        import textual  # noqa: F401,PLC0415

        return True
    except ImportError:
        return False


def can_start(presentation: Optional[Any] = None) -> tuple[bool, str]:
    """能不能進 TUI。回 `(可以, 原因)` —— **原因要能印給使用者看**。

    ⚠️ 純函式,所以「被 pipe 時不進 TUI」這件事測得到,而不是要真的開一個終端機。
    """
    seen = presentation if presentation is not None else _cli_ui.detect()
    if not seen.banner:
        # banner=False 已經涵蓋:非 TTY、NO_COLOR、TERM=dumb、--format json/csv
        return False, f"not an interactive terminal ({seen.reason})"
    if not textual_available():
        return False, "the [cli] extra is not installed (pip install twmarketdata[cli])"
    return True, "interactive terminal with textual"


def build_app(*, datasets: list[dict], on_fetch: Any) -> Any:
    """組出 TUI app。`on_fetch(dataset_id, ticker) -> (rows, provenance)` 由呼叫方注入。

    ⚠️ 注入而不是在這裡取數:TUI 是呈現層,一旦它自己會取數,就會出現第二條
    取數路徑,而那條路徑不會有 `twmd get` 的 as_of 警告與缺口提示。
    """
    from textual.app import App, ComposeResult  # noqa: PLC0415
    from textual.containers import Horizontal, Vertical  # noqa: PLC0415
    from textual.widgets import DataTable, Footer, Header, Static  # noqa: PLC0415

    class TwmdTui(App):  # type: ignore[misc]
        CSS = """
        Screen { layout: vertical; }
        #body { height: 1fr; }
        #left { width: 34; border: solid $accent; }
        #right { width: 1fr; }
        #results { height: 1fr; border: solid $accent; }
        #provenance { height: 7; border: solid $accent; color: $text-muted; }
        """
        BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh"),
                    ("/", "focus_list", "Datasets")]
        TITLE = "TWMD · 台股資料 · 可驗證 · 為 AI agent 而生"

        def compose(self) -> ComposeResult:  # pragma: no cover - UI 組裝
            yield Header()
            with Horizontal(id="body"):
                with Vertical(id="left"):
                    yield DataTable(id="datasets")
                with Vertical(id="right"):
                    yield DataTable(id="results")
                    yield Static("select a dataset to load rows", id="provenance")
            yield Footer()

        def on_mount(self) -> None:  # pragma: no cover - UI 生命週期
            table = self.query_one("#datasets", DataTable)
            table.cursor_type = "row"
            table.add_columns("dataset", "free")
            for entry in datasets:
                table.add_row(entry["id"], "yes" if entry.get("key_free") else "-")
            self.query_one("#results", DataTable).cursor_type = "row"

        def on_data_table_row_selected(self, event: Any) -> None:  # pragma: no cover
            table = self.query_one("#datasets", DataTable)
            if event.data_table.id != "datasets":
                return
            dataset_id = str(table.get_row_at(event.cursor_row)[0])
            self._load(dataset_id)

        def _load(self, dataset_id: str) -> None:  # pragma: no cover
            results = self.query_one("#results", DataTable)
            results.clear(columns=True)
            provenance = self.query_one("#provenance", Static)
            try:
                rows, note = on_fetch(dataset_id, None)
            except Exception as exc:  # noqa: BLE001 - TUI 不該用 traceback 招呼使用者
                provenance.update(f"could not load {dataset_id}: {exc}")
                return
            if not rows:
                provenance.update(f"{dataset_id}: no rows (that is not the same as no coverage)")
                return
            columns = list(rows[0].keys())[:8]
            results.add_columns(*columns)
            for row in rows:
                results.add_row(*[str(row.get(c, "")) for c in columns])
            provenance.update(note)

        def action_refresh(self) -> None:  # pragma: no cover
            self.notify("pick a dataset on the left to reload it")

        def action_focus_list(self) -> None:  # pragma: no cover
            self.query_one("#datasets", DataTable).focus()

    return TwmdTui()


def run() -> int:
    """進入 TUI。**不能進就說為什麼並退回選單**,不是安靜地什麼都不做。"""
    ok, reason = can_start()
    if not ok:
        from . import _cli_interactive  # noqa: PLC0415

        _cli_ui.hint(f"(TUI unavailable: {reason} — falling back to the guided menu)",
                     _cli_ui.detect())
        return _cli_interactive.run()

    import twmd  # noqa: PLC0415

    free = set(twmd.runnable_without_key())
    datasets = [{"id": key, "key_free": key in free} for key in twmd.datasets()]

    def _fetch(dataset_id: str, ticker: Optional[str]) -> tuple[list[dict], str]:
        info = twmd.get(dataset_id)
        samples = twmd.free_tier_symbols()
        chosen = ticker or (samples[0] if info.entity_is_stock_ticker else None)
        client = twmd.Client()
        try:
            result = client.dataset(dataset_id, ticker=chosen, limit=50)
        finally:
            client.close()
        from ._cli import _rows_of  # noqa: PLC0415

        rows = _rows_of(result)
        coverage = " → ".join(x for x in (info.coverage_min, info.coverage_max) if x)
        note = (f"dataset: {dataset_id}   coverage: {coverage or 'unmeasured'}\n"
                f"as_of: (none — latest revision; pass --as-of on `twmd get` to pin it)\n"
                f"verify: https://api.twmarketdata.com/v2/proof/checkpoints")
        return rows, note

    build_app(datasets=datasets, on_fetch=_fetch).run()
    return 0
