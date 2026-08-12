# 發布前阻斷清單

**狀態:不可發布。** 里程碑 2 的程式碼已完成並測試通過,但 PyPI 上已經有一個同名、同 import 名的**已發布套件**,發布前必須由 owner / director 裁決。

---

## 阻斷 1(必須裁決):`twmarketdata` 0.1.0 已經在 PyPI 上,而且 import 名就是 `twmd`

實測(2026-08-12):

```
GET https://pypi.org/pypi/twmarketdata/json
  name        twmarketdata
  version     0.1.0
  license     MIT
  uploaded    2026-07-21T11:31:00Z
  author      TW Market Data
  homepage    https://twmarketdata.com

GET https://pypi.org/pypi/twmd/json  →  HTTP 404   (twmd 這個名字沒被佔)
```

原始碼在 `/Volumes/DEV_USB/Projects/twmd-python-client`(branch `main`,3 commits),本機 site-packages 也裝著它。**這是我們自己的套件**,不是別人佔名。

### 它跟本 repo 撞在哪

| | 已發布 0.1.0 | 本 repo 0.2.0 |
|---|---|---|
| dist 名 | `twmarketdata` | `twmarketdata` ← **同名** |
| import 名 | `twmd` | `twmd` ← **同名** |
| 授權 | **MIT** | **Apache-2.0** ← 變更 |
| HTTP 套件 | **httpx** | **requests** ← 變更 |
| 公開 API | `Client.get_dataset / get_all / iter_pages / list_datasets / is_key_free`、`access` 模組(`OPEN_DATASETS` 2 支、`SAMPLE_TICKERS`、`access_tier`、`explain`、`provenance`)、`frames.to_dataframe`、10 個 `Twmd*Error` | `Client.dataset` + 82 支具名方法、`registry`/`capabilities`、`TwmdFrame`/`Meta`、`compat.finmind`、另一組錯誤階層 |

以現況直接發 0.2.0 會造成三件事:

1. **既有使用者的程式碼會壞。** `from twmd import access`、`to_dataframe`、`TwmdAPIError`、`iter_pages`、`get_all`、`list_datasets` 在 0.2.0 都不存在。
2. **授權從 MIT 變 Apache-2.0。** owner 持有著作權,向前變更是可以的(0.1.0 永遠維持 MIT),但這是使用者看得見的變動,要有意識地做。
3. **相依從 httpx 換成 requests**,`transport=` 參數的型別契約(`httpx.BaseTransport`)也跟著失效。

### 三個選項

| | 作法 | 代價 |
|---|---|---|
| **A** | 發成 **`twmd`**(PyPI 可用),`twmarketdata` 0.1.0 原封不動 | 兩個 dist 都提供 `twmd` 模組,同時安裝會互相覆蓋 —— **不建議** |
| **B**(建議) | 續發 `twmarketdata` **0.2.0**,保留 0.1.0 全部公開 API 當 deprecated alias(`get_dataset`/`get_all`/`iter_pages`/`list_datasets`/`access`/`to_dataframe` + 錯誤名),CHANGELOG 寫明破壞性變更 | 要補一層相容 shim(約半天),但沒人被弄壞 |
| **C** | 把本 repo 的成果**併回 `twmd-python-client`** 當 0.2.0,維持 MIT,商標免責照樣放 NOTICE(NOTICE 不是 Apache 專屬) | 少一次授權變更;但 repo 要合併,且放棄 Apache 的專利授權條款 |

**我的建議:B**。理由:`twmarketdata` 已有 PyPI 頁面、下載數與 README badge(GEO 資產已經在累積),換名等於重來;而 0.1.0 的公開面很小(6 個方法 + 一個 access 模組),做成 alias 成本低。授權則照 director 裁決走 Apache-2.0 —— 但這是**不可逆的公開動作**,需要 owner 明確再點一次頭,不能由我代決。

**在此裁決前,本 repo 的 `pyproject.toml` 不得用於 `twine upload`。**

---

## 阻斷 2(等 key):key-gated 項目

| 項目 | 卡在 |
|---|---|
| 付費層 cassette 錄製 | 受限測試 key |
| 9 列 low 信心映射逐列驗證 | 受限測試 key |
| `client_unsafe` → `client` 升級評估(`company_news`、`dividends`、`stock_delisting_lifecycle`) | 受限測試 key |
| pro / max 範例 | 受限測試 key |
| `ResponseMeta` 那四個 `X-TWMD-*` header 是否只在帶 key 時出現 | 受限測試 key |

紀律(已定):owner 在 enterprise console 自產受限 key → 錄 cassette → 用完刪 key。cassette 進 repo 前 redact `X-API-Key` / `Authorization`,`tools/audit_public_repo.py` 在 CI 第一關擋住未遮罩者。enterprise key 不進 repo、不進 chat。

---

## 已通過的發布前檢查

```
$ python tools/audit_public_repo.py
ok   secrets
ok   retired base URL
ok   package contents
Audit clean: no credentials, no retired base URL, package ships only the client.

$ python tools/check_registry_drift.py
registry matches the live API (82 datasets checked)

$ pytest -m "not network"     96 passed
$ pytest -m network            9 passed   (真端點、免 key)
```
