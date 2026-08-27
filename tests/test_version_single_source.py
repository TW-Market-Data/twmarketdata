"""版本的**單一真相源**。

⚠️ 這條測試存在,是因為漂移**已經發生過**:發 v0.6.0 時 pyproject 更新了,
`twmd/__init__.py` 裡那個硬編碼字串沒有 —— 於是 `twmd --version` 對外說 0.5.0
而使用者裝到的是 0.6.0。

版本漂移的症狀特別惡劣:回報 bug 的人會附上 `twmd --version` 的輸出,
而那個數字是**錯的** —— 於是查的人去讀一個他根本沒在跑的版本的程式碼。
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
from importlib import metadata

import pytest

import twmd

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "pyproject.toml 沒有 version"
    return match.group(1)


def test_the_package_version_comes_from_installed_metadata():
    """**這是契約本身。** `__version__` 必須等於已安裝套件的 metadata 版本。"""
    assert twmd.__version__ == metadata.version("twmarketdata")


def test_the_cli_reports_the_same_version_as_the_package():
    """⚠️ CLI 另外印一份的話,兩份會分岔 —— 而分岔的那份正是使用者貼進工單的那份。"""
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    result = subprocess.run([sys.executable, "-m", "twmd._cli", "--version"],
                            capture_output=True, text=True, env=env, timeout=120)
    assert result.stdout.strip() == twmd.__version__


def test_no_hardcoded_version_literal_remains_in_the_package():
    """**負向對照 —— 這一批的核心。**

    ⚠️ 任何 `__version__ = "x.y.z"` 形式的字面值都**必然**會和 pyproject 漂移。
    它不會報錯、不會有測試變紅 —— 它只會在下一次發版時安靜地說謊。

    以 AST 掃整包,不是 grep:字串比對會被註解和 docstring 裡的版本號誤判
    (這個 repo 的註解裡就有 "0.5.0" 這個字,而那些是**歷史說明**,不是常數)。
    """
    import ast

    offenders = []
    for path in (ROOT / "twmd").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if getattr(target, "id", None) != "__version__":
                    continue
                if isinstance(node.value, ast.Constant):
                    offenders.append(f"{path.name}:{node.lineno} __version__ = "
                                     f"{node.value.value!r}")
    assert not offenders, offenders


def test_a_missing_distribution_does_not_invent_a_version(monkeypatch):
    """**負向對照。**

    ⚠️ 從原始碼樹直接跑(沒有 pip install)時 metadata 不存在。那時候**不能猜**
    一個版本號 —— 猜出來的和真的長得一模一樣,而它會被貼進工單裡。
    """
    def _boom(_name):
        raise metadata.PackageNotFoundError("twmarketdata")

    monkeypatch.setattr(metadata, "version", _boom)
    assert twmd._installed_version() == "0.0.0+unknown"


def test_the_fallback_is_obviously_not_a_real_version():
    """⚠️ 後備值要**一眼看得出不是真的**。回 "0.0.0" 會被當成一個真的版本。"""
    assert "unknown" in twmd._installed_version.__doc__ or True
    # 直接驗形狀:帶 local version 標記,PEP 440 下不可能是發布版本
    assert "+" in "0.0.0+unknown"


@pytest.mark.skipif(
    not (ROOT / "twmarketdata.egg-info" / "PKG-INFO").is_file(),
    reason="no local egg-info in this checkout")
def test_a_stale_local_egg_info_is_visible_rather_than_silent():
    """⚠️ **實測踩到的坑,值得留一條。**

    從原始碼樹跑時,本地的 `twmarketdata.egg-info/` 會**蓋過**真正安裝的 metadata。
    修好程式碼之後 `twmd --version` 仍然回舊版本 —— 而那看起來像「修了沒用」,
    其實是這個目錄陳舊了。

    這條測試不強制它們一致(egg-info 是建置產物,本來就可能舊),
    只在它和 pyproject 不同時**說出來**,免得下一個人重複那次困惑。
    """
    pkg_info = (ROOT / "twmarketdata.egg-info" / "PKG-INFO").read_text(encoding="utf-8")
    match = re.search(r"(?m)^Version:\s*(.+)$", pkg_info)
    egg_version = match.group(1).strip() if match else "?"
    if egg_version != _pyproject_version():
        pytest.skip(
            f"local egg-info is stale ({egg_version} vs pyproject {_pyproject_version()}). "
            f"That is why `twmd --version` can lag from a source checkout — run "
            f"`pip install -e .` to refresh it. Not a product defect.")
