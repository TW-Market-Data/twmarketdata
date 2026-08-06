[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md)

# twmd — Python 台股市場資料客戶端

[![PyPI](https://img.shields.io/pypi/v/twmarketdata)](https://pypi.org/project/twmarketdata/)
[![Python](https://img.shields.io/pypi/pyversions/twmarketdata)](https://pypi.org/project/twmarketdata/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/twmarketdata)](https://pypi.org/project/twmarketdata/)

**[TW Market Data](https://twmarketdata.com)** API 的官方 Python 客戶端 —— 上市（TWSE）／
上櫃（TPEx）行情、財務報表、法人買賣、估值與因子資料,共 80+ 資料集,以 pandas
DataFrame 回傳。**五檔範例股免金鑰即可查詢**,一行就能試。

```bash
pip install twmarketdata
```
```python
from twmd import Client
Client().get_dataset("twse-daily-price", symbol="2330", limit=5)   # 免金鑰
```

**開始使用:** [免費 API 金鑰](https://twmarketdata.com) · [方案定價](https://twmarketdata.com/pricing) · [文件](https://twmarketdata.com/docs) · [資料集目錄](https://twmarketdata.com/datasets) · [MCP / AI agents](https://twmarketdata.com/docs/tools-and-mcp)

---

`twmd` 透過 HTTP 取回已發布的資料集,並回傳為 pandas DataFrame。它是一層資料取回的
傳輸層,供研究與教育用途。它按 API 發布的樣子取回紀錄,不做任何分析、評分、排序或
詮釋。資料代表什麼、以及要不要據以行動,完全是呼叫端自己的工作與責任。

回應會帶著 API 本身的 `lineage.not_investment_advice` 旗標,本客戶端原封保留。

## 安裝

```bash
pip install twmarketdata
```

發行套件名為 `twmarketdata`;匯入的套件名是 `twmd`:

```python
import twmd
```

純 Python。相依只有 `httpx` 與 `pandas` —— 無編譯擴充、無系統函式庫,可安裝於受限
沙箱中。

需要 Python 3.9 以上。相依下限刻意壓低（`pandas>=1.5`、`httpx>=0.27`）,好讓它能裝進
既有環境而不強迫升級;CI 會用這些下限精準釘住跑完整測試,讓它們保持誠實而非空談。

有一個不是我們能修的注意事項:pandas 1.5 的 wheel 是對 numpy 1.x 的 C ABI 編譯的,在
numpy 2 下匯入會以 `numpy.dtype size changed` 失敗。若你被釘在 pandas 1.x,請一併釘
`numpy<2`。pandas 2.2.2 以後則可在不限制 numpy 2 的情況下運作。

## 快速開始 —— 免金鑰

選定的資料集上,五檔範例股免憑證即可取用,以下零設定就能跑:

```python
from twmd import Client

client = Client()
df = client.get_dataset("twse-daily-price", symbol="2330", limit=5)

print(df[["date", "open", "high", "low", "close", "volume_shares"]])
print(df.attrs["data_as_of"])       # 資料新鮮度日期
print(df.attrs["lineage"])          # 提供者、來源端點、來源資料表
```

## 為什麼選 twmd

- **官方來源,明白標示。** 每筆回應都帶 `lineage` —— 提供者、官方來源端點、來源資料表
  —— 以及 `data_as_of` 新鮮度日期。不捏造、不內插、不回填。
- **只取資料,不夾帶觀點。** 本客戶端只取回資料;不產生任何分數、訊號或建議。資料
  代表什麼,由你自己判斷。
- **誠實的涵蓋範圍。** 資料集只回報它實際擁有的內容。缺漏就顯示為缺漏 —— 絕不用零
  或別檔的資料列填補。
- **純 Python。** `httpx` + `pandas`,無編譯擴充 —— 到處都能裝,連受限沙箱也行。CI 在
  Linux／macOS／Windows 上跨 Python 3.9–3.13 驗證。
- **也為 AI agent 而生。** 同一批資料可透過 [MCP](https://twmarketdata.com/docs/tools-and-mcp)
  與 [`llms.txt`](https://twmarketdata.com/llms.txt) 索引取用,讓 agent 直接探索並查詢
  資料集。

## 認證

在環境變數中設定你的金鑰;它絕不寫入磁碟、也不記入日誌:

```bash
export TWMD_API_KEY="sk_live_..."
```

`Client()` 會自動讀取。你也可以明確傳入 `Client(api_key=...)`。未設金鑰時,客戶端以
免金鑰模式運作,可取用下方列出的資料集。

## 免金鑰取用對照表

免金鑰取用是**逐資料集**界定的,不是全域逐檔。同一檔股票在某個資料集免金鑰,在另一個
資料集可能就需要金鑰。以下為 2026-07-21 對線上 API 實測:

| 層級 | 資料集 | 免金鑰可查的股票 |
| --- | --- | --- |
| 開放 | `security-master`、`market-index` | 任意 |
| 範例 | `twse-daily-price`、`tpex-daily-price`、`monthly-revenue` | 僅 `2330`、`2317`、`2454`、`0050`、`2603` |
| 需金鑰 | 其餘全部,含 `institutional-flow`、`market-prices`、`financial-metrics`、`income-statement`、`balance-sheet` | 無 |

請求前先檢查:

```python
from twmd import is_key_free

is_key_free("twse-daily-price", "2330")     # True
is_key_free("twse-daily-price", "1101")     # False —— 不在範例股之列
is_key_free("security-master", "1101")      # True —— 開放資料集
is_key_free("institutional-flow", "2330")   # False —— 需金鑰
```

不在表中的資料集一律視為需金鑰,這是安全的預設。客戶端絕不會據此擋下請求 —— 它只
用這張表在事後解釋 401。

## DataFrame 與中繼資料

紀錄變成資料列。回應信封中的其餘一切都保留在 `df.attrs`。

API 使用**兩種信封形狀**,`twmd` 兩者都會透明處理:

```python
# rows / count —— twse-daily-price、tpex-daily-price、monthly-revenue
df.attrs["dataset"]       # "twse_daily_price"
df.attrs["count"]         # 紀錄筆數
df.attrs["data_as_of"]    # 資料新鮮度日期
df.attrs["source_role"]   # 例如 "official_twse"
df.attrs["lineage"]       # 提供者、官方來源、來源端點、資料表
df.attrs["meta"]          # 最後交易日、市場狀態

# items / row_count —— security-master、market-index
df.attrs["dataset_id"]                  # "security-master"
df.attrs["row_count"]                   # 紀錄筆數
df.attrs["as_of_date"]                  # 快照日期
df.attrs["survivorship_bias_warning"]   # API 提出的完整性注意事項
```

信封內容因資料集而異 —— `monthly-revenue` 只送 `dataset`、`rows`、`count` —— 所以讀
`attrs` 要防禦性一點。

`items` 變體中的紀錄含巢狀物件（`security_identity`、`market_identity`、`index_level`）。
它們維持為 dict 值的欄位而不攤平,好讓 DataFrame 反映 API 實際送出的內容。需要時
再展開:

```python
import pandas as pd
identity = pd.json_normalize(df["security_identity"])
```

注意 `security-master` 帶有 `survivorship_bias_warning`,聲明目前的主檔並非時間點完整
（point-in-time complete）。它原封呈現在 `attrs` 上;用該資料集做歷史分析前請先檢查。

## 錯誤

```python
from twmd import Client, TwmdAuthError, TwmdPaymentRequired

try:
    df = client.get_dataset("institutional-flow", symbol="2330")
except TwmdAuthError as exc:
    print(exc.error_code)   # "missing_api_key" 或 "invalid_api_key"
    print(exc.body)         # 解碼後的回應內容,原文照錄
```

每個 `TwmdAPIError` 子類別 —— 下表除最後一列外的每一列 —— 都提供 `.status_code`、
`.body`（解碼後、未修改的內容）、`.text` 與 `.error_code`。`TwmdTransportError` 與
`TwmdConfigError` 直接衍生自 `TwmdError`,因為沒有收到回應,故不帶上述屬性。

| 狀態碼 | 例外 | 是否重試 |
| --- | --- | --- |
| 401 | `TwmdAuthError` | 否 |
| 402 | `TwmdPaymentRequired` | 否 |
| 404 | `TwmdNotFoundError` | 否 |
| 422 | `TwmdValidationError` | 否 |
| 429 | `TwmdRateLimitError` | 是 |
| 5xx | `TwmdServerError` | 是 |
| 網路失敗 | `TwmdTransportError` | 是 |

重試採用帶抖動的指數退避。`Retry-After` 標頭 —— 不論是 RFC 7231 的 delta-seconds 或
HTTP-date 形式 —— 會覆蓋前述機制並被精確遵守,不加抖動、不縮短,因為比伺服器允許的
時間更早重試,比等太久更糟。若它要求超過 `RETRY_AFTER_MAX`（120 秒）,客戶端會停止
並拋出伺服器的錯誤,而非卡住數分鐘。

401 訊息會標註你所請求之資料集與股票的免金鑰狀態,讓「我忘了帶金鑰」能與「那檔
股票不在範例股之列」區分開來。

### 401 與 402 的差別

兩者意義不同,解法也不同:

- **401** —— 沒帶金鑰,或金鑰無效。用註冊／新增金鑰來解決。
- **402** —— 金鑰有效,但**方案未包含**該資料集。用升級方案來解決。

線上 402 回應內容（2026-07-21 驗證）:

```json
{
  "error": "not_entitled_for_dataset",
  "message": "您的方案未包含此資料集…",
  "payment": {
    "price": "pro",
    "credits_url": "https://twmarketdata.com/pricing",
    "purchase_hint": "upgrade_plan"
  }
}
```

整段內容原文保留在 `.body`。為方便起見,`payment` 物件及其欄位也暴露在例外上 —— 一律
讀 API 實際送來的值,絕不捏造:

```python
except TwmdPaymentRequired as exc:
    exc.payment        # payment 物件,或 None
    exc.price          # "pro"
    exc.credits_url    # "https://twmarketdata.com/pricing"
    exc.purchase_hint  # "upgrade_plan"
    exc.body           # 完整回應,未修改
```

## 來源標記

傳入 `source` 為每個請求標上產生它的整合來源,讓發布者能歸因流量:

```python
client = Client(source="ecosys/tradingagents")
```

它會作為 `source` 查詢參數附在每個請求上。`get_dataset` 上逐次的 `source=` 會覆蓋
客戶端層級的值。它是一個普通查詢參數 —— 不改變回應、不進入資料回應的
`request_context.filters`、也不帶任何使用者資訊。不設就不送。

## 分頁

```python
df = client.get_all("twse-daily-price", symbol="2330", limit=1000)

for page in client.iter_pages("twse-daily-price", symbol="2330", limit=500):
    process(page)
```

API 不發布游標:任何回應或 OpenAPI 文件中都沒有 `cursor` 或 `next_cursor` 欄位。分頁
是 `limit`/`offset`,而 `offset` 經實測在免金鑰端點上被**忽略** —— `offset=3` 回傳與
`offset=0` 相同的紀錄。

所以這裡的分頁是防禦性的。它依文件推進 `offset`,然後在以下兩種情況停止:某頁回傳
筆數少於 `limit`,或某頁重複了前一頁的第一筆紀錄 —— 那是 `offset` 被靜默忽略的特徵。
對忽略 `offset` 的端點,這會剛好產生一頁,那是正確結果而非失敗。`max_pages` 為迴圈
設上限。

## `as_of`

`get_dataset()` 接受 `as_of` 引數並將它作為查詢參數轉送。**它的適用範圍很窄。** 依
2026-07-21 實測:

- `as_of` 僅宣告於四個端點 —— `income-statement`、`cash-flow-statement`、
  `balance-sheet`、`financials` —— 且都需要 API 金鑰。
- 在其餘每個端點它都不是已宣告的參數。API 會靜默忽略未知的查詢參數,回 200 而非
  422,所以在那些端點傳 `as_of` 沒有可觀察的效果、也不會報錯。
- 它在那四個已宣告端點上的行為,本專案**未驗證**,因為沒有憑證可實測。

請把 `as_of` 當成「已轉送但未確認」,而非通用的時間點查詢機制。回應中的 `data_as_of`
欄位是資料新鮮度日期,是另一回事。

## 開發

```bash
pip install -e ".[test]"
pytest -m "not live"    # 離線,不連網
pytest -m live          # 打真正的 API,僅免金鑰路徑
```

live 測試會斷言免金鑰對照表的一個樣本 —— 七組資料集／股票配對 —— 仍與 API 提供的
一致,所以這些表面的漂移會以測試失敗浮現。它是一條絆線,不是完整覆蓋:五檔範例股僅
對 `twse-daily-price` 驗證,而三個列為需金鑰的資料集是假定而非實測（見
`access.PRESUMED_KEY_REQUIRED_DATASETS`,以及 `access.provenance()` 可分辨兩者）。

## 適用範圍

本套件負責取回資料。它不產生任何關於任何證券的建議、預測、訊號、估值或觀點,其回傳
的內容也不應被如此解讀。資料供研究與教育用途;在據以行動前,請對照原始來源查核。
使用底層 API 受 TW Market Data 自身條款規範。

## 授權

MIT
