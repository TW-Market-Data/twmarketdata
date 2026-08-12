# TWMD Python SDK — 設計文件 v1

**狀態**:待 director 審核(通過後才進實作)
**日期**:2026-08-12
**套件名**:`twmd`(備案 `twmarketdata`,PyPI 佔名由 owner 親查)
**授權**:Apache-2.0(專利授權 + NOTICE 放商標免責)
**對應工單**:`WORKORDER_Python_SDK_twmd_20260812.md` 里程碑 1

---

## 0. 目的、範圍、非目標

**目的**:讓 `pip install twmd` 兩行拿到 DataFrame,涵蓋 82 支可售資料集,提供 FinMind 相容層讓既有程式碼幾乎照跑,並把 point-in-time 正確性做成 SDK 的一級功能。

**範圍**:Python 客戶端。薄封裝 + 正規化 + PIT 語義 + 相容層 + 型別 + 測試 + 範例。

**非目標(明確不做)**:

- 不做比較頁、不做競品評分、不在任何文件裡貶損 FinMind。
- 不假冒、不盜用 FinMind 商標。相容層映射的是**呼叫介面**(方法名/參數名),不含其程式碼,不打包其程式碼。
- 不在 SDK 內補值、內插、forward-fill 或以零填缺口。
- 不代替使用者決定資料夠不夠用 —— 缺口與截斷一律 surface。

---

## 1. 三支柱 → 可驗收條件

| 支柱 | 可驗收條件(每條對得到一個測試) |
|---|---|
| ① 簡單如 FinMind | `pip install twmd` 後,兩行程式碼對 2330 拿到 DataFrame,免 API key。82 支全部有具名方法。 |
| ② FinMind 相容層 | `mapping/finmind_map.csv` 每一列都標了級別與驗證來源;D 級一律 `NotMappedError`,測試斷言它不回空 DataFrame。 |
| ③ 嚴謹 PIT | `as_of` 三態行為各有測試;`data_gaps` 有來源標記;截斷回應必定帶 `truncated=True`。 |

---

## 2. 先行實測:這份設計建立在哪些事實上

以下全部在 2026-08-12 對 `https://api.twmarketdata.com` 免 key 實測而得,原始證據存在 `mapping/sources/`。**工單原本的幾個假設需要修正**:

### 2.1 端點形狀

| 假設 | 實測 |
|---|---|
| `/v2/datasets/<slug>`(底線) | 實際是 kebab-case,且 **6/82 的 route 不等於 kebab(dataset_key)** |
| 82 支 | `/v2/datasets` 註冊表有 **125** 筆、OpenAPI 掛了 **119** 個 dataset route、MCP `sellable+queryable` 是 **82**。本 SDK 的 82 = 可售集合 |

route 不等於 key 的 6 支(SDK 用 `dataset_key` 當方法名,route 由 registry 查表,route 漂了不會壞掉):

| dataset_key | 實際 route |
|---|---|
| `financial_ratios` | `/v2/datasets/financial-metrics` |
| `margin_short_total` | `/v2/datasets/total-margin-short` |
| `industry_index` | `/v2/datasets/index-classification` |
| `issuer_profiles` | `/v2/datasets/issuer-profile` |
| `interest_rate_snapshots` | `/v2/datasets/interest-rate-snapshot` |
| `taifex_final_settlement` | `/v2/datasets/futures-final-settlement` |

### 2.2 參數異質性(SDK 的主要價值來源)

82 支之中:

- 實體參數:`ticker` 26、`symbol` 13、`cb_id` 3、`contract` 3、`issuer` 4、`index_code` 2、`contract_code` 1、**無實體參數 30**(市場級/維度表)
- 起始日期參數:`date_from` 47、`start_date` 11、`start_period` 2、`data_month` 1、**無日期參數 21**
- `as_of` / `as_of_date`:**只有 17 支**
- `include_data_gaps`:**只有 22 支**
- `offset`:**只有 9 支**;其餘 73 支只有 `limit`(上限 5000)

### 2.3 回應 envelope 不一致

免 key 探測拿到 200 的少數幾支就出現 **4 種不同的 envelope**,而且**列陣列的 key 有三種**:

| 樣本 | 列的 key | 其他欄位 |
|---|---|---|
| `twse_daily_price` / `tpex_daily_price` | `rows` | `count, data_as_of, source_role, lineage, meta.market_status` |
| `monthly_revenue` | `rows` | `count`(**沒有** lineage / data_as_of) |
| `index_constituents` | `items` | `dataset_id, row_count, held_policy` |
| `market_index` | `data` | `data_count, dataset_id, envelope, known_gaps, quality, warnings, request_context` |

**設計後果**:`Response.rows` 的抽取必須是「依序嘗試 `rows` → `items` → `data` → `results`」而不是寫死,而且 lineage/gaps 只有部分資料集會給 —— 沒給的一律標 `unknown`,**不能自己編一個**。

### 2.4 PIT 的實況

- `monthly_revenue` 的 `knowledge_time_field` 是 `as_of_date`,而 describe 明講「這是所屬期別不是公告日」;免 key 抓 2330 回來的列,`announcement_date` 與 `source_publish_date` **都是 null**。→ 這支不能假裝 PIT 可用。
- `attention_disposal_events` / `day_trading_suspension` / `margin_short_cover_date`:事件日是**生效日或未來日**,表上沒有公告日欄 → 官方 describe 明講 `as_of` 應被拒絕。
- `company_industry_exposures` / `company_peer_groups`:整表沒有日期欄,無法回放。
- `macro_worldbank`:來源回溯修訂歷史年度,非 PIT 紀錄。

這幾條不是缺陷,是**必須被 SDK 忠實轉述的事實**。

### 2.5 錯誤與速率限制

| 狀況 | 回應 |
|---|---|
| 免 key 打付費資料集 | `401 {"error":"missing_api_key", "message":"缺少 API 金鑰。…或改打五檔免金鑰試玩端點。"}` |
| 短時間併發過多 | `403 {"error":"temporarily_blocked"}` |

`403 temporarily_blocked` 是本次探測**自己觸發**出來的(4 併發掃 82 支即中),而且封鎖持續數十分鐘未解。因此 SDK **必須**內建預設併發上限與退避,否則使用者第一次跑批次就會被擋,還會誤以為是沒有權限。

第一輪探測有 60 支落在封鎖期間,結果不可用;**已於冷卻後以每 4 秒一發重跑補齊,零封鎖、82 支全數取得可信結果**(過程中沒有拿 403 當成「需要 key」充數)。

### 2.6 免 key 實際可跑的是哪些(82 支全測)

| 結果 | 支數 |
|---|---|
| 免 key 且回到資料 | **16** |
| 免 key 回 200 但空集合 | 3 |
| 需要 key(乾淨 401) | 63 |

免 key 有資料的 16 支全部是 `tier=free`,README 範例只能綁在這 16 支上:
`security_master`、`trading_calendar`、`monthly_revenue`、`twse_daily_price`、`index_constituents`、`trading_rules_reference`、`bond_convertible_reference`、`broker_branch_reference`、`warrants_reference`、`company_industry_exposures`、`company_peer_groups`、`securities_firm_master`、`fund_etf_metadata`、`issuer_classification`、`stock_delisting_lifecycle`、`stock_split_par_value_events`。

回 200 空集合的 3 支,空是**正確的**不是缺口:`tpex_daily_price`(2330 在上市不在上櫃)、`market_index`(要 `index_code` 不吃 `symbol`)、`investor_conference_calendar`(2330 在該滾動視窗內無場次)。SDK 不會把這種空當成 gap 回報。

**另有 3 支標示 `tier=free` 卻回 401**:`valuation_data`、`issuer_profiles`(兩者皆 active)、`industry_index`(registry_status=planned)。已列入 `api_inconsistencies.md` 第 K 項。

---

## 3. Client

```python
from twmd import Client

c = Client()                      # 無 key:免費層五檔示範
c = Client("你的_api_key")         # 有 key:依方案解鎖
c = Client(api_key=..., timeout=30, max_retries=5, max_concurrency=2)
```

- key 來源優先序:參數 > `TWMD_API_KEY` 環境變數 > 無 key 模式。**key 永不寫進 repo、永不進 log、repr 一律遮罩**。
- 認證:`X-API-Key` header。
- 免費層示範代號(由 owner 裁定,所有 README 範例只用這五檔):
  **2330 台積電、2317 鴻海、2454 聯發科、0050 元大台灣50、2603 長榮**。
  無 key 時傳入其他代號 → `FreeTierSymbolError`,訊息列出這五檔,不靜默回空。
- **併發與退避**:預設 `max_concurrency=2`;遇 `403 temporarily_blocked` 與 `429` 走指數退避 + jitter,預設最多 5 次;`Retry-After` 有給就照給的等。逾時預設 30s。
- **分頁**:`offset` 只有 9 支有。SDK 的 `paginate()` 對這 9 支自動翻頁;其餘 73 支打到 `limit`(上限 5000)就是被截斷 →
  **回應必定帶 `truncated=True`,並在 log 與 `Meta.warnings` 說明「這批不完整」**。不做假的翻頁。

---

## 4. 錯誤型別

```
TwmdError
├── TwmdConfigError
│   └── FreeTierSymbolError        無 key 卻查非示範代號
├── TwmdAuthError
│   ├── MissingApiKeyError         401 missing_api_key
│   └── TierRequiredError          需要更高方案;帶 required_tier 與資料集頁連結
├── TwmdRequestError
│   ├── DatasetNotFoundError       404 / 不在 82 之列
│   └── UnsupportedParameterError  傳了該支不支援的參數(不靜默丟掉)
├── TwmdRateLimitError             403 temporarily_blocked / 429(附退避資訊)
├── TwmdServerError                5xx
├── PointInTimeUnavailable         該資料集無法支援 as_of(見 §6)
└── NotMappedError                 compat 專用:FinMind 呼叫在 TWMD 無對應
```

`UnsupportedParameterError` 是刻意的:82 支參數不一,使用者傳 `start=` 給一支沒有日期參數的資料集時,**寧可報錯也不要默默忽略**再回一份看起來正常的資料。

---

## 5. 回應型別

### 5.1 `TwmdFrame`

```python
class TwmdFrame(pandas.DataFrame):
    _metadata = ["twmd"]          # 讓 metadata 撐過 slicing / copy
    @property
    def _constructor(self): return TwmdFrame
```

- `isinstance(df, pandas.DataFrame)` 為真 → 支柱①「兩行有 DataFrame」成立,既有生態全部可用。
- `df.twmd` 是 `Meta`。
- **誠實揭露**:pandas 某些 op(`merge`、`groupby.apply` 等)仍可能丟掉 `_metadata`。因此同一份 Meta 也掛在 `c.last_response.meta`,docstring 明寫這個限制,不假裝萬無一失。
- `raw=True` → 回原始 dict;未安裝 pandas → 回 `list[dict]` + 一個獨立的 `Meta`(核心不強制依賴 pandas)。

### 5.2 `Meta`

```python
@dataclass(frozen=True)
class Meta:
    dataset: str                  # dataset_key
    route: str
    row_count: int
    truncated: bool               # limit 打滿且無 offset → True
    tier_required: str            # free / starter / pro / max / developer / enterprise
    registry_status: str          # active / partial / planned / private_beta
    # --- PIT ---
    as_of_requested: date | None
    as_of_mode: str               # server | client | unsupported
    as_of_applied: bool
    knowledge_time_field: str | None
    point_in_time_safe: bool | None
    pit_caveat: str | None        # describe_dataset 的 PIT 註記,原文轉述
    # --- 覆蓋與缺口 ---
    data_gaps: list[Gap]
    gaps_source: str              # server | client_derived | unknown
    coverage_min: str | None
    coverage_max: str | None
    # --- 來源 ---
    data_as_of: str | None
    source_role: str | None
    lineage: dict | None
    warnings: list[str]
    request_id: str | None
```

沒拿到的欄位一律 `None` / `"unknown"`,**不推測、不預設為樂觀值**。

---

## 6. PIT 規格(支柱 ③)

### 6.1 `as_of` 三態

`as_of=` 在每支資料集上的語義由 registry 決定,並在 `Meta.as_of_mode` 回報:

| mode | 支數 | 行為 |
|---|---|---|
| `server` | 16 | 透傳 `as_of` / `as_of_date`,由 server 過濾 |
| `client` | 45 | server 沒有 as_of,但 `point_in_time_safe=true` 且 `knowledge_time_field` 存在於已發布 schema → 取回後在本地依該欄過濾 |
| `client_unsafe` | 8 | 有宣告 knowledge 欄位,但 `point_in_time_safe=false` → **預設拒絕**,需明確 `as_of_policy="declared_field"` 才放行 |
| `client_unverified` | 5 | 宣告了 knowledge 欄位,但該欄位不在已發布 schema → **執行期檢查**:回應列裡真有該欄就照 client 模式過濾,沒有就 `PointInTimeUnavailable` |
| `unsupported` | 8 | 整表無時間軸,或官方 describe 明講 as_of 不成立 → **直接 raise `PointInTimeUnavailable`** |

- `client_unsafe`(8):`attention_disposal_events`、`company_news`、`corporate_actions`、`dividends`、`industry_chain`、`macro_worldbank`、`monthly_revenue`、`stock_delisting_lifecycle`
- `client_unverified`(5):`industry_index`、`market_index`、`mops_major_event`、`security_master`、`valuation_data`
- `unsupported`(8):`company_industry_exposures`、`company_peer_groups`、`day_trading_suspension`、`margin_short_cover_date`、`margin_short_total`、`price_enhanced`、`stock_split_par_value_events`、`subsidiary_investment`

**`client_unsafe` 是這份設計裡最重要的一格。** 舉例:`monthly_revenue` 宣告的 knowledge 欄位是 `as_of_date`,但 describe 明講「`as_of_date` 為**所屬期別非公告日**,回測請以公告日對齊」。若照一般規則在本地用 `as_of_date <= as_of` 過濾,等於用「營收所屬月份」當知識軸 —— **那正是 as_of 本來要防的未來函數**(六月營收在六月底就被當成已知,實際上要到七月十日前才公告)。同理 `attention_disposal_events` / `corporate_actions` 的 `event_date` 是生效日、`industry_chain` 的 `capture_date` 是我方觀察日、`macro_worldbank` 會被來源回溯修訂。

因此規則是機械化的、不是個案:**`point_in_time_safe=false` 的資料集,一律不准在本地默默做 as_of**。呼叫端要嘛不帶 as_of 自行對齊公告日,要嘛明確 opt-in 並承擔風險。

這 8 支裡有 3 支(`company_news`、`dividends`、`stock_delisting_lifecycle`)的宣告欄位看起來確實是真的揭露時點(`published_at` / `announcement_date`),很可能可以升級成 `client`。但**上游標的是 `point_in_time_safe=false`,在拿測試 key 逐列驗證前不自行升級** —— 保守的那一邊才是誠實的那一邊。

**語義優先於參數清單**:`subsidiary_investment` 的 route **接受** `as_of_date` 參數,但 describe 明講它是「每家公司一筆的季更屬性、fact date 是所屬期別而非揭露日」,`knowledge_time_field` 為 null 且 `point_in_time_safe=false`。接受這個參數會讓呼叫端誤以為真的做了回放 —— 因此 SDK **拒絕**,並在錯誤訊息裡說明原因。這條規則寫在 `tools/build_mapping.py`,不是個案硬編。

**兩個額外的誠實檢查**:

1. **client 模式 + 截斷**:先被 `limit` 截斷、再本地過濾,會把「其實有資料」誤判成「那天還沒有」。→ 這種情況一律 `TruncatedPointInTimeWarning`,並在 Meta 標 `as_of_applied` 與 `truncated` 兩者皆真。
2. **knowledge 欄位全 null**(如 `monthly_revenue` 的 `announcement_date`)→ `PITDataMissingWarning`,不當作「通過」。

### 6.2 `data_gaps`

| gaps_source | 適用 | 作法 |
|---|---|---|
| `server` | 22 支有 `include_data_gaps` | 透傳,原樣回報 |
| `client_derived` | 日頻 + 有實體參數者 | 以 `trading_calendar` 為基準推算缺漏交易日 |
| `unknown` | 其餘 | 明確標 unknown |

三種情況都**不補值**。`Gap` 攜帶 `start / end / reason`,`reason` 區分「來源未發布」與「本表未載入」——例如 `margin_system_stats.maintenance_ratio` 是官方 describe 註明的 NULL(honest gap),`shareholding_concentration` 早於 2026-08 的週次是**來源不留檔、永遠取不到**,不是缺資料。兩者訊息不同。

---

## 7. 方法清單(82 支)與 codegen

完整表:**`mapping/datasets_82.csv`**(30 欄,含 route、tier、grain、knowledge_time_field、point_in_time_safe、as_of_mode、data_gaps 支援、分頁方式、真實參數名、欄位清單、覆蓋範圍、免 key 探測結果)。

### 7.1 三層 API

```python
# L1 泛型(逃生門,永遠不會漏支)
c.dataset("monthly_revenue", ticker="2330", start="2020-01-01")

# L2 具名方法 × 82(由 registry 生成 .py + .pyi)
c.monthly_revenue(ticker="2330", start="2020-01-01")
c.shareholding_concentration(ticker="2330")

# L3 人工精選別名(ergonomic,約 12 支高頻)
c.daily_price("2330", start="2020-01-01")   # 合併 TWSE+TPEx,加 market 欄
```

- **方法名 = `dataset_key`**,不用 route 名(route 會漂,key 穩定)。
- `c.daily_price` 合併兩市場並加 `market` 欄;**跨市場不靜默去重**(同代號同日若兩市場都有,兩列都保留並在 `Meta.warnings` 標示)。`c.twse_daily_price` / `c.tpex_daily_price` 保留原樣。

### 7.2 參數正規化

對外統一 `ticker=` / `start=` / `end=` / `as_of=` / `limit=`;registry 記錄每支的真實參數名做轉譯:

| SDK 參數 | 實際可能對到 |
|---|---|
| `ticker` | `ticker` / `symbol` / `cb_id` / `contract` / `issuer` / `index_code` / `contract_code` |
| `start` | `date_from` / `start_date` / `start_period` / `data_month` |
| `end` | `date_to` / `end_date` / `end_period` |
| `as_of` | `as_of` / `as_of_date` / (client-side) |

該支不支援的參數 → `UnsupportedParameterError`。

### 7.3 能力矩陣公開

```python
twmd.capabilities("monthly_revenue")
# {'tier': 'free', 'status': 'active', 'as_of': 'client',
#  'data_gaps': 'unsupported', 'pagination': 'limit_only',
#  'point_in_time_safe': False, 'knowledge_time_field': 'as_of_date',
#  'pit_caveat': '月營收於次月10日前公告,as_of_date 為所屬期別非公告日…'}
```

同一份資料印進 README 與 docstring。使用者不必試錯就知道每支能做什麼、不能做什麼。

### 7.4 registry 從哪來、怎麼重生

`twmd/_registry.json` 由 `tools/build_mapping.py` 從四個來源 join 而成,全部存在 `mapping/sources/`:

| 來源 | 提供 |
|---|---|
| `GET /v2/datasets` | status、coverage、entity_count、source_name |
| `GET /openapi.json` | 真實 route 與每支的真實參數 |
| `GET /v2/datasets/{key}/schema` | 欄位清單(82/82 全數取得) |
| `twmd.describe_dataset`(MCP) | grain、knowledge_time_field、point_in_time_safe、PIT 註記、中文名、tier |

**CI 每日重跑並 diff**:route 改名、參數增減、tier 變動、新資料集上架 → 自動開 issue。registry 內含產生時間與來源 URL,可稽核。

### 7.5 tier 與狀態

| tier | 支數 | | registry_status | 支數 |
|---|---|---|---|---|
| free | 22 | | active | 75 |
| starter | 17 | | partial | 5 |
| pro | 17 | | planned | 1 |
| max | 16 | | private_beta | 1 |
| developer | 9 | | | |
| enterprise | 1 | | | |

- `partial` / `planned` / `private_beta` 的資料集,方法照樣存在,但 docstring 與 `Meta.registry_status` 明寫狀態,**不讓使用者以為拿到的是完整序列**。
- 401/402 → `TierRequiredError`,訊息帶 `required_tier` 與該資料集頁連結。

---

## 8. FinMind 相容層

完整表:**`mapping/finmind_map.csv`**。

### 8.1 驗證方式(不憑記憶)

FinMind 側的方法名與參數名,來自對已安裝的開源套件 **FinMind v2.0.7** 做 **signature introspection**(`tools/introspect_finmind.py`,2026-08-12)——讀 `DataLoader` 的公開方法簽章與 `Dataset` enum,**不呼叫其服務、不使用其憑證、不複製也不打包其原始碼**。取得 **102 個公開方法、105 個 dataset enum**。

CSV 每一列都帶 `finmind_verified_by`(`method_signature` / `dataset_enum`)與 `finmind_source`(`introspection of FinMind v2.0.7 @ 2026-08-12`),任何人可重跑驗證。

### 8.2 五級與執行期行為

| 級 | 意義 | `compat.finmind` 行為 |
|---|---|---|
| **A** one_to_one | 同 grain 同語義,只差欄位名 | 直接回,欄位改名 |
| **B** transformed | 同一事實但形狀/單位不同 | 轉換後回,`Meta` 標 `mapping=transformed` 與轉了什麼 |
| **C** substituted | 無同名對應,TWMD 以別的方式涵蓋 | 正常回 + `CompatSubstitutionWarning`(講清楚換成哪支、差在哪) |
| **D** unavailable | 82 支之中無對應 | `raise NotMappedError`,**絕不回空 DataFrame 假裝成功** |
| **E** twmd_only | TWMD 有,而在**已 introspect 的 v2.0.7 介面**中找不到對應項目 | 中性列於附錄,不做比較、不評價 |

E 級的措辭是刻意的:陳述的是「在我實際 introspect 到的那個介面裡沒有對應項目」這個可複驗的觀察,不是對該產品的價值判斷。

### 8.2.1 目前分佈(144 列)

| 級別 | 列數 |
|---|---|
| A one_to_one | 19 |
| B transformed | 17 |
| C substituted | 24 |
| D unavailable | 46 |
| E twmd_only | 38 |

信心:`high` 111、`medium` 24、`low` 9。FinMind 側驗證來源:`method_signature` 93、`dataset_enum` 13,**沒有任何一列是未驗證的**。82 支 TWMD 資料集全部被這張表涵蓋到(A–E 至少出現一次)。

D 級 46 列裡佔比最大的是三類:盤中/逐筆/即時(tick、snapshot、K 線、五秒指數)、期權法人與大額交易人明細、非台股市場(美股/歐股/日股/英股/黃金/原油/情緒指數)。這三類目前不在 82 支可售集合內,compat 一律 `NotMappedError` 並在訊息中說明類別,不猜、不代打。

### 8.3 用法

```python
from twmd.compat import finmind as fm

df = fm.taiwan_stock_daily(stock_id="2330", start_date="2020-01-01")   # A 級,直接對應
df = fm.taiwan_stock_financial_statement(stock_id="2330", ...)         # B 級,wide→long 還原成長格式
df = fm.taiwan_option_vix(start_date="2024-01-01")                     # C 級,warning:derived ATM IV,非官方 VIX
df = fm.taiwan_stock_trading_daily_report(...)                         # D 級,NotMappedError
```

`confidence` 欄位標 `high / medium / low`;**`low` 的映射在拿到測試 key 逐列比對前不出貨**(先以 `NotMappedError` 出貨,訊息說明「候選映射待驗證」),寧可少對也不要對錯。

### 8.4 商標與免責(寫進 README 第一段與 NOTICE)

> `twmd.compat.finmind` provides source-compatible call signatures so existing code can run against TWMD.
> This project is **not affiliated with, endorsed by, or sponsored by FinMind**. "FinMind" is referenced
> nominatively, solely to identify the interface being made compatible. No FinMind source code is included
> or redistributed. The mapping table records, for every entry, whether a TWMD equivalent exists, is a
> substitute, or is unavailable.

---

## 9. 型別與封裝

- 全量型別註記 + `py.typed`;L2 的 82 支方法連同參數與回傳型別一併生成 `.pyi`。
- mypy strict 進 CI。
- 相依:`requests`(必要)、`pandas`(選用 extra,無 pandas 時核心可用)。

---

## 10. 測試策略

| 層 | 作法 | 需不需要 key |
|---|---|---|
| 單元測試 | 參數轉譯、envelope 抽取(rows/items/data 三種)、PIT 三態、gap 推算、錯誤映射 | 否 |
| 免費層 smoke | 對真端點跑免 key 可跑的那幾支,`limit=1`,五檔示範代號,序列化 + 退避 | 否(CI 可跑) |
| 付費層 | VCR 式 cassette 錄製回放。**key 只在 owner 本機錄製時使用,cassette 進 repo 前掃描並遮罩,key 不進 repo** | 錄製時要 |
| registry 漂移 | 每日 CI 重抓 openapi + /v2/datasets,與 registry diff | 否 |

付費層的範例與測試在測試 key 核發前一律標 **`recorded pending test key`**,不寫看起來能跑但其實沒驗證過的 code。

> 註:先前外洩的那把 key 本專案完全未使用(owner 另行輪替),此處刻意不記錄其任何片段。本次所有探測皆為免 key 呼叫。

---

## 11. 打包 / CI / 範例

- Apache-2.0;`NOTICE` 放商標免責。
- 語意化版本;`0.x` 期間 compat 層的 `low` 信心映射可能變動,在 CHANGELOG 明列。
- CI:lint + mypy strict + 單元測試 + 免費層 smoke + registry 漂移偵測。
- `examples/`:每個範例只用五檔示範代號與免 key 可跑的資料集;需要 key 的範例在檔頭標明所需 tier。
- README:綁定句 **「TWMD = TW Market Data = twmarketdata.com」**;quickstart;三支柱;FinMind 相容範例;能力矩陣摘要。

---

## 12. 附錄與待辦

- **`mapping/datasets_82.csv`** — 82 支方法清單與能力矩陣
- **`mapping/finmind_map.csv`** — FinMind 相容映射表(A–E 五級)
- **`mapping/api_inconsistencies.md`** — API 一致性差異清單,供 director 轉獨立工單(SDK 這側照樣先抹平,兩邊並行)
- **`mapping/sources/`** — 全部原始證據(openapi、registry、82 份 schema、FinMind introspection、免 key 探測結果)

### 待 owner / director 處理

| # | 事項 | 卡住什麼 |
|---|---|---|
| 1 | PyPI `twmd` 佔名 | 套件名最終確認(設計不受影響) |
| 2 | 受限測試 key 核發 | 付費層 cassette 錄製、`low` 信心映射的逐列驗證、pro/max 範例 |
| 3 | 免費層五檔的實際可用資料集清單 | 見 `datasets_82.csv` 的 `free_tier_probe_2026_08_12` 欄;README 範例只能綁在探測為可跑的那些 |
