"""把錯誤變成「下一步」。

## 為什麼猜測值得做

`Unknown dataset 'monthly-revenue'` 對一個剛裝好的人來說是死路 —— 他打的是
**對的東西的錯拼法**(dash vs underscore 是這支 CLI 最常見的一種),而錯誤訊息
只告訴他「沒有」。加一句「你是不是要 monthly_revenue?」把死路變成一步。

⚠️ 猜測只在**夠接近**時給。一個對每個輸入都硬湊一個建議的系統,會在使用者
真的打錯資料集名字時建議一個毫不相干的,而他會照著打第二次。
"""

from __future__ import annotations

import difflib
from typing import Iterable, Optional

#: 相似度門檻。0.6 是 difflib 的常用起點;拉低會開始建議無關的名字,
#: 而一個亂猜的建議比不猜更浪費時間。
_CUTOFF = 0.6


def suggest(unknown: str, candidates: Iterable[str], *, limit: int = 3) -> list[str]:
    """最接近的幾個名字。**先做 dash/underscore 正規化再比。**

    `monthly-revenue` 和 `monthly_revenue` 的字面相似度已經很高,但正規化之後
    是完全相同 —— 那應該排第一,而不是和其他形近的名字混在一起。
    """
    target = str(unknown or "").strip().lower()
    if not target:
        return []
    pool = [str(c) for c in candidates]
    normalised = {c: c.lower().replace("-", "_") for c in pool}
    exact = [c for c in pool if normalised[c] == target.replace("-", "_")]
    if exact:
        return exact[:limit]
    close = difflib.get_close_matches(target.replace("-", "_"),
                                      list(normalised.values()), n=limit, cutoff=_CUTOFF)
    reverse = {v: k for k, v in normalised.items()}
    return [reverse[c] for c in close if c in reverse][:limit]


def unknown_dataset_message(unknown: str, candidates: Iterable[str]) -> tuple[str, list[str]]:
    """訊息 + 下一步。回 (message, next_steps)。"""
    guesses = suggest(unknown, candidates)
    if guesses:
        head = f"No dataset called '{unknown}'. Did you mean [bold]{guesses[0]}[/bold]?"
        steps = [f"twmd describe {guesses[0]}"]
        if len(guesses) > 1:
            head += f" (or: {', '.join(guesses[1:])})"
    else:
        head = f"No dataset called '{unknown}'."
        steps = ["twmd datasets            # list everything",
                 "twmd datasets --free-only   # what works with no key"]
    return head, steps


def access_message(kind: str, *, dataset: str = "", upgrade_url: str = "",
                   sample_tickers: Optional[Iterable[str]] = None) -> tuple[str, list[str]]:
    """沒金鑰 vs 方案不夠 —— **兩種完全不同的處置,所以分開講。**

    ⚠️ 把它們寫成同一句「access denied」,是讓一個只要設環境變數的人去買方案,
    或讓一個已經付費的人反覆檢查金鑰。
    """
    samples = list(sample_tickers or ["2330", "2317", "2454", "0050", "2603"])
    if kind == "auth":
        return (
            "[bold]No API key.[/bold] That is a configuration gap, not a billing one.",
            [f"export TWMD_API_KEY=sk_live_...    # then re-run",
             "twmd datasets --free-only          # or use what needs no key at all",
             f"twmd get twse_daily_price --ticker {samples[0]} --limit 5   # works right now"],
        )
    if kind == "entitlement":
        head = (f"[bold]Your plan does not cover {dataset or 'this dataset'}.[/bold] "
                f"Your key is fine — this is a plan limit.")
        steps = [f"twmd get twse_daily_price --ticker {samples[0]} --limit 5   "
                 f"# these {len(samples)} tickers are free"]
        if upgrade_url:
            steps.append(f"{upgrade_url}    # upgrade with the same email; no reconnect needed")
        return head, steps
    return ("", [])


def render_next_steps(steps: Iterable[str]) -> str:
    return "\n".join(f"  {step}" for step in steps)
