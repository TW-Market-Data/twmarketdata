"""CLI 的呈現層 —— **只管好看,絕不碰資料。**

## 鐵律:機器拿到的永遠是乾淨的

同一個 `twmd` 要同時服務真人和腳本。決定「現在是誰在看」的規則全部集中在
`detect()`,而不是散在每個指令裡各判一次 —— 散開就會有某一條路忘了判,
而那條路會在某個人的 pipeline 裡吐出色碼,把 CSV 解析壞掉。

    無色、無 banner 的條件(任一成立即可):
      * `--format json` / `--format csv`   —— 要的是機器格式
      * stdout 不是 TTY(被 pipe 或導向檔案)
      * `NO_COLOR` 有設(no-color.org 的約定:**有設就算**,值是什麼都不管)
      * `TERM=dumb`

⚠️ 「被 pipe 就沒有 TTY」是這件事唯一可靠的訊號。用「有沒有 CI 環境變數」之類的
啟發式判斷,會在有人本機 `| less` 的時候猜錯,而猜錯的方向是把色碼寫進資料。

## rich 是可選的

`pip install twmarketdata` 只裝 requests。`[cli]` 才裝 rich/questionary。
沒裝的時候**不是壞掉**,是退回純文字 —— 一個因為沒裝 UI 套件就跑不動的 CLI,
會讓「我只是想取個數」的人卡在安裝上。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Optional, Sequence

MACHINE_FORMATS = frozenset({"json", "csv"})

#: 柔和色。⚠️ 不用高飽和原色:終端機背景深淺不一,亮紅配深背景會糊掉,
#: 而 CLI 的顏色只有在**看得清楚**時才有意義。
STYLE_POSITIVE = "green"
STYLE_NEGATIVE = "red"
STYLE_HEADER = "bold cyan"
STYLE_DIM = "dim"
STYLE_WARN = "yellow"

#: banner 的漸層(由深到淺的青綠)。柔和、對比足夠,而且在淺色背景也讀得到。
_BANNER_GRADIENT = ("#0e7490", "#0891b2", "#06b6d4", "#22d3ee", "#67e8f9", "#a5f3fc")

_BANNER = r"""
 ████████╗██╗    ██╗███╗   ███╗██████╗
 ╚══██╔══╝██║    ██║████╗ ████║██╔══██╗
    ██║   ██║ █╗ ██║██╔████╔██║██║  ██║
    ██║   ██║███╗██║██║╚██╔╝██║██║  ██║
    ██║   ╚███╔███╔╝██║ ╚═╝ ██║██████╔╝
    ╚═╝    ╚══╝╚══╝ ╚═╝     ╚═╝╚═════╝
"""


@dataclass(frozen=True)
class Presentation:
    """這一次要用什麼樣子輸出。`reason` 是給 `--help`/除錯用的人話。"""

    colour: bool
    banner: bool
    reason: str

    @property
    def plain(self) -> bool:
        return not self.colour


def rich_available() -> bool:
    """`[cli]` extra 裝了沒。沒裝不是錯誤,是退回純文字。"""
    try:
        import rich  # noqa: F401,PLC0415

        return True
    except ImportError:
        return False


def questionary_available() -> bool:
    try:
        import questionary  # noqa: F401,PLC0415

        return True
    except ImportError:
        return False


def detect(*, fmt: Optional[str] = None, stream: Any = None,
           env: Optional[dict] = None) -> Presentation:
    """要不要上色、要不要 banner。**單一判斷點。**

    參數全部可注入,所以測試不需要真的去接一個終端機 —— 而「被 pipe 的時候
    會怎樣」正是最需要測、也最難手動驗的那一條。
    """
    environ = os.environ if env is None else env
    out = sys.stdout if stream is None else stream

    if str(fmt or "").lower() in MACHINE_FORMATS:
        return Presentation(False, False, f"--format {fmt} is a machine format")
    if "NO_COLOR" in environ:
        # no-color.org:**存在**就算數,不看值 —— 檢查值等於發明一個別人不知道的規則。
        return Presentation(False, False, "NO_COLOR is set")
    if str(environ.get("TERM", "")).lower() == "dumb":
        return Presentation(False, False, "TERM=dumb")
    try:
        tty = bool(out.isatty())
    except Exception:  # noqa: BLE001 — 問不出來就當作不是終端機(往乾淨的方向錯)
        tty = False
    if not tty:
        return Presentation(False, False, "stdout is not a terminal")
    if not rich_available():
        return Presentation(False, False, "the [cli] extra is not installed")
    return Presentation(True, True, "interactive terminal")


# --------------------------------------------------------------------------- banner

def render_banner(presentation: Presentation, *, version: str, status: str) -> str:
    """大字 + 一行狀態。**不上色時回空字串** —— 純資料模式不該有裝飾。

    ⚠️ 靜態一次印完,沒有動畫、沒有重繪:一個會重畫的 banner 在 `script`、
    在慢速 SSH、在被記錄的終端機裡會變成一團控制碼。
    """
    if not presentation.banner:
        return ""
    lines = [line for line in _BANNER.strip("\n").splitlines() if line.strip()]
    if not rich_available():
        return "\n".join(lines)

    from rich.text import Text  # noqa: PLC0415

    rendered = Text()
    for index, line in enumerate(lines):
        rendered.append(line + "\n", style=_BANNER_GRADIENT[index % len(_BANNER_GRADIENT)])
    rendered.append("   TW Market Data · 台股資料 · 可驗證 · 為 AI agent 而生\n",
                    style=STYLE_DIM)
    rendered.append(f"   twmd {version} · {status}\n", style=STYLE_DIM)
    return rendered  # type: ignore[return-value]


def print_banner(presentation: Presentation, *, version: str, status: str) -> None:
    body = render_banner(presentation, version=version, status=status)
    if not body:
        return
    if rich_available() and not isinstance(body, str):
        _console().print(body)
    else:
        print(body)


def _console(stderr: bool = False, highlight: bool = True):
    from rich.console import Console  # noqa: PLC0415

    # ⚠️ `highlight=False` 給說明文字用。rich 的自動高亮會把 `2010-01` 這種
    # 日期裡的數字挑出來上色,於是一行原本安靜的來源註記變成花的,
    # 而顏色在這裡本來是要留給漲跌的。
    return Console(stderr=stderr, soft_wrap=False, highlight=highlight)


# --------------------------------------------------------------------------- 表格

def _looks_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return False
    try:
        float(text)
        return True
    except ValueError:
        return False


def _sign_style(value: Any) -> Optional[str]:
    """負值紅、正值綠。**零沒有顏色** —— 零不是好消息也不是壞消息。"""
    if not _looks_numeric(value):
        return None
    number = float(str(value).strip().replace(",", "").replace("%", ""))
    if number > 0:
        return STYLE_POSITIVE
    if number < 0:
        return STYLE_NEGATIVE
    return None


#: 會依正負上色的欄位。⚠️ **白名單**,不是「所有數字都上色」——
#: 把股價或成交量塗成綠色沒有意義(它們永遠是正的),只會讓真正有意義的
#: 漲跌顏色被稀釋掉。
_SIGNED_COLUMN_HINTS = ("change", "chg", "yoy", "mom", "return", "pct", "diff", "net",
                        "漲跌", "報酬", "增減")


def _is_signed_column(name: str) -> bool:
    lowered = str(name).lower()
    return any(hint in lowered for hint in _SIGNED_COLUMN_HINTS)


#: 一張表在標準終端機裡放得下的欄數。⚠️ 這不是美感問題:13 欄擠進 80 字元會
#: 讓每格被折成 3 個字,那份輸出比純文字更難讀 —— 顏色救不了一張讀不了的表。
_MAX_TABLE_COLUMNS = 7


def _fit_columns(rows: Sequence[dict], columns: Sequence[str]) -> tuple[list[str], int]:
    """挑出要顯示的欄,並回報總共有幾欄。

    ⚠️ **少顯示幾欄是可以的,不說就不行。** 呼叫方會把「顯示 X 欄 / 共 Y 欄」
    印出來,而完整資料一律用 `--format json`。一張安靜地少了六欄的表,
    讀起來就是完整的那一張。
    """
    names = list(columns)
    if len(names) <= _MAX_TABLE_COLUMNS:
        return names, len(names)
    # 整欄皆空的先丟 —— 它們佔寬度卻不帶資訊。
    non_empty = [c for c in names if any(r.get(c) not in (None, "") for r in rows)]
    keep = non_empty or names
    return keep[:_MAX_TABLE_COLUMNS], len(names)


def print_table(rows: Sequence[dict], columns: Sequence[str], presentation: Presentation, *,
                title: str = "", subtitle: str = "") -> bool:
    """彩色表格。回 True 表示印了;False 表示呼叫方要自己走純文字。"""
    if not presentation.colour or not rich_available():
        return False

    from rich.table import Table  # noqa: PLC0415

    shown, total = _fit_columns(rows, columns)
    caption = subtitle or ""
    if len(shown) < total:
        note = f"showing {len(shown)} of {total} columns · --format json for all"
        caption = f"{caption}  ·  {note}" if caption else note
    table = Table(title=title or None, header_style=STYLE_HEADER, title_style=STYLE_HEADER,
                  caption=caption or None, caption_style=STYLE_DIM, expand=False)
    numeric = {c: all(_looks_numeric(r.get(c)) for r in rows if r.get(c) not in (None, ""))
               for c in shown}
    columns = shown
    for column in columns:
        # 數字右對齊 —— 靠左的數字要一位一位比,而對齊過的一眼看得出量級。
        table.add_column(str(column), justify="right" if numeric.get(column) else "left",
                         overflow="fold")
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            text = "" if value is None else str(value)
            style = _sign_style(value) if _is_signed_column(column) else None
            cells.append(f"[{style}]{text}[/{style}]" if style else text)
        table.add_row(*cells)
    _console().print(table)
    return True


def print_provenance(presentation: Presentation, *, dataset: str, as_of: Optional[str],
                     coverage: str = "", verify_url: str = "") -> None:
    """「這筆怎麼來的」—— 資料集、涵蓋、as_of。

    ⚠️ 沒帶 as_of 時要**明講是最新修訂值**,不是留白。留白讀起來像
    「這個問題不適用」,而它其實是「你拿到的可能不是當時看得到的數字」。
    """
    if not presentation.colour:
        return
    parts = [f"dataset: {dataset}"]
    if coverage:
        parts.append(f"coverage: {coverage}")
    parts.append(f"as_of: {as_of}" if as_of else "as_of: (none — latest revision)")
    if verify_url:
        parts.append(f"verify: {verify_url}")
    _console(highlight=False).print("  ·  ".join(parts), style=STYLE_DIM)


# --------------------------------------------------------------------------- 訊息

def _emit(message: str, style: str, presentation: Presentation) -> None:
    """訊息一律走 stderr —— stdout 是資料的地盤。"""
    if presentation.colour and rich_available():
        _console(stderr=True).print(message, style=style)
    else:
        print(_strip_markup(message), file=sys.stderr)


def _strip_markup(message: str) -> str:
    """把 rich 的 `[style]…[/style]` 拿掉,純文字模式不該看到標記殘骸。"""
    import re  # noqa: PLC0415

    return re.sub(r"\[/?[a-zA-Z0-9 _#]+\]", "", message)


def warn(message: str, presentation: Presentation) -> None:
    _emit(message, STYLE_WARN, presentation)


def error(message: str, presentation: Presentation) -> None:
    _emit(message, STYLE_NEGATIVE, presentation)


def hint(message: str, presentation: Presentation) -> None:
    _emit(message, STYLE_DIM, presentation)
