# 0.2.0 發布清單(owner 執行)

**憑證全程由 owner 自己來 —— PyPI token 與 API key 都不進 repo、不進 chat、不交給任何 agent。**

發布會覆蓋一個**已上線的套件**(`twmarketdata` 0.1.0,2026-07-21 上線,MIT)。0.2.0 是 Apache-2.0,且換掉了整個 client 實作。0.1.0 的公開面全部保留為 deprecated alias,所以既有安裝升級不會壞 —— 但這仍是不可逆的公開動作,請照順序走完。

---

## 0. 前置(尚未完成,擋住發布)

- [ ] **受限測試 key 產出**(enterprise console,**不是** enterprise key 本身)
- [ ] `export TWMD_API_KEY=<受限 key>`(**在你自己的 shell**,不要貼進任何對話)
- [ ] `python tools/record_cassettes.py` — 錄付費層 cassette,自動 redact
- [ ] `TWMD_API_KEY=... python tools/verify_low_confidence.py --all` — 驗 7 條未驗證映射
- [ ] `python examples/03_backtest_ready_fundamentals.py` / `04_chips_and_derivatives.py` —— 跑過後把檔頭的 `RECORDED PENDING TEST KEY` 拿掉、註解換成真實輸出
- [ ] **回 console 刪掉那把受限 key**

---

## 1. 綠燈檢查(全部要過)

```bash
python tools/audit_public_repo.py          # 零祕密、無退役 base_url、wheel 只含 client
python tools/check_registry_drift.py       # 82 支與 live API 相符
pytest -m "not network"                    # offline 全綠
pytest -m network                          # 真端點免 key 全綠
mypy twmd                                  # strict
python tools/gen_registry.py && python tools/gen_methods.py && python tools/gen_compat_map.py
git diff --exit-code -- twmd/_registry.json twmd/_methods.py twmd/_methods.pyi twmd/compat/_finmind_map.json
```

最後一行必須**無輸出** —— 有 diff 代表有人手改了生成檔。

- [ ] 全部通過
- [ ] `git status` 乾淨

---

## 2. 拿掉發布阻斷

`pyproject.toml` 開頭有六行 `# DO NOT PUBLISH YET` banner,擋住誤上傳。確認上面都綠了再刪:

```bash
python - <<'PY'
p = "pyproject.toml"
lines = open(p).read().splitlines(True)
assert lines[0].startswith("# DO NOT PUBLISH"), "banner already removed?"
open(p, "w").writelines(lines[7:])   # banner is 6 comment lines + 1 blank
PY
head -3 pyproject.toml     # 應該直接是 [build-system]
```

- [ ] banner 已移除
- [ ] `PUBLISH_BLOCKERS.md` 的阻斷 1 標記為已裁決(B 案)、阻斷 2 已清空

---

## 3. 版本與變更紀錄

- [ ] `pyproject.toml` 的 `version = "0.2.0"`
- [ ] `twmd/__init__.py` 的 `__version__ = "0.2.0"`(兩者必須一致)
- [ ] `CHANGELOG.md` 的 `## 0.2.0 — unreleased` 改成今天日期

```bash
python -c "
import re, twmd
v = re.search(r'version = \"([^\"]+)\"', open('pyproject.toml').read()).group(1)
assert v == twmd.__version__, (v, twmd.__version__)
print('version consistent:', v)"
```

---

## 4. 建置與本機驗證 —— ✅ 已於 2026-08-12 跑過

> 這一節不需要憑證,已代跑完畢,結果如下。發布前建議再跑一次(拿掉 banner 之後),指令原樣保留。
>
> ```
> version consistency   pyproject 0.2.0 == __version__ 0.2.0     ✅
> python -m build       twmarketdata-0.2.0-py3-none-any.whl (71 KB)
>                       twmarketdata-0.2.0.tar.gz (85 KB)        ✅
> twine check           both PASSED                              ✅
> wheel 內容            27 檔,全部在 twmd/ 與 dist-info 之內      ✅
>                       py.typed / _registry.json / _methods.pyi /
>                       compat/_finmind_map.json 都在;無 CSV、無 tests/tools/mapping
> metadata              License-Expression: Apache-2.0
>                       License-File: LICENSE, NOTICE
>                       Requires-Python: >=3.9;Requires-Dist: requests>=2.31.0  ✅
> sdist                 LICENSE / NOTICE / README.md / pyproject.toml 均在  ✅
> 乾淨環境冒煙          daily_price('2330') 120 列、compat 可 import、
>                       0.1.0 alias 可用、PIT 拒絕與過濾都正確      ✅
> ```
>
> **這一節抓到一個真 bug**:`twmd/compat/_finmind_map.json` 原本沒被打包
> (setuptools 的 package-data key 只涵蓋自己那個 package),安裝後
> `from twmd.compat import finmind` 會 FileNotFoundError。已修,並加了一條
> 會走訪 package 的回歸測試。**原始碼樹的測試抓不到這個 —— 這就是發布前
> 一定要真的 build 的理由。**



```bash
python -m pip install -U build twine
rm -rf dist build *.egg-info
python -m build                 # 產生 sdist + wheel
python -m twine check dist/*    # metadata / README 渲染檢查
```

**wheel 內容稽核** —— 只能有 client,不能有證據檔或工具:

```bash
python - <<'PY'
import zipfile, glob
whl = glob.glob("dist/*.whl")[0]
names = zipfile.ZipFile(whl).namelist()
bad = [n for n in names
       if not (n.startswith("twmd/") or ".dist-info/" in n)]
assert not bad, bad
assert any(n.endswith("twmd/py.typed") for n in names), "py.typed missing"
assert any(n.endswith("_registry.json") for n in names), "registry missing"
assert not any(n.endswith(".csv") for n in names), "evidence CSV leaked into the wheel"
print("wheel clean:", len(names), "files")
PY
```

裝到乾淨環境冒煙:

```bash
python -m venv /tmp/twmd-smoke && /tmp/twmd-smoke/bin/pip install -q dist/*.whl
/tmp/twmd-smoke/bin/python -c "
from twmd import Client
import twmd
df = Client().daily_price('2330')          # 免 key
assert len(df) > 0
assert twmd.__version__ == '0.2.0'
assert hasattr(Client(), 'get_dataset')    # 0.1.0 alias 還在
print('smoke ok:', len(df), 'rows')"
```

- [ ] build 成功、`twine check` 通過
- [ ] wheel 稽核通過
- [ ] 乾淨環境冒煙通過

---

## 5. 先發 TestPyPI(強烈建議)

```bash
python -m twine upload --repository testpypi dist/*
python -m venv /tmp/twmd-test && /tmp/twmd-test/bin/pip install -q \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ twmarketdata==0.2.0
/tmp/twmd-test/bin/python -c "import twmd; print(twmd.__version__)"
```

- [ ] TestPyPI 安裝與 import 正常

---

## 6. 正式發布

```bash
python -m twine upload dist/*
```

驗證真的取代了 0.1.0:

```bash
python -m venv /tmp/twmd-live && /tmp/twmd-live/bin/pip install -q -U twmarketdata
/tmp/twmd-live/bin/python -c "
import twmd
print('version:', twmd.__version__)
print('datasets:', len(twmd.datasets()))
from twmd import Client
print('0.1.0 alias intact:', hasattr(Client(), 'get_dataset'))"
```

- [ ] `twmarketdata 0.2.0` 已上線 PyPI
- [ ] 從 0.1.0 升級後 0.1.0 的 API 仍可用

---

## 7. 發布後

- [ ] `git tag -a v0.2.0 -m "0.2.0" && git push --tags`
- [ ] GitHub repo 開源(Apache-2.0),README 綁定句就位:
      **TWMD = TW Market Data = twmarketdata.com**
- [ ] 把 `twmd-python-client`(0.1.0 原始碼)指向這個 repo,或封存並在 README 註明後續在此
- [ ] 確認 PyPI 頁面顯示 Apache-2.0,且 README 渲染正常
- [ ] `mapping/api_inconsistencies.md`(A–P 共 16 項)轉「API 一致性」工單

---

## 若要撤回

PyPI **不允許重新上傳同一版本號**。發現問題就發 0.2.1,不要試圖覆蓋。
真的必須讓 0.2.0 消失,只能 `yank`(使用者已裝的不受影響,新安裝會跳過):

```bash
# PyPI 網頁 → Manage → Releases → Yank
```
