# 附錄:TWMD v2 API 一致性差異清單

**用途**:SDK 這側已決定單方面抹平這些差異(不等 API 改)。本清單供 director 轉為獨立的「API 一致性」工單另軌推進。
**量測日期**:2026-08-12
**量測方式**:全部免 key 唯讀呼叫。原始證據在 `sources/`(`twmd_openapi.json`、`twmd_v2_datasets.json`、`twmd_schemas_82.json`、`smoke_nokey.json`)。
**範圍**:82 支可售資料集(`sellable=true` 且 `queryable=true`)。

---

## A. 實體參數名有 7 種

| 參數名 | 支數 |
|---|---|
| `ticker` | 26 |
| `symbol` | 13 |
| `issuer` | 4 |
| `cb_id` | 3 |
| `contract` | 3 |
| `index_code` | 2 |
| `contract_code` | 1 |
| (無實體參數) | 30 |

`ticker` 與 `symbol` 指的是同一件事(證券代號),卻在不同 route 上用不同名字。使用者換一支資料集就要換參數名。

**SDK 對策**:對外統一 `ticker=`,registry 查表轉譯。

---

## B. 日期參數名有 5 種

| 起始參數 | 支數 |
|---|---|
| `date_from` | 47 |
| `start_date` | 11 |
| `start_period` | 2 |
| `data_month` | 1 |
| (無日期參數) | 21 |

對應的結束參數同樣分裂為 `date_to` / `end_date` / `end_period`。另有 `start_month` / `end_month` 出現在部分 route(如 `monthly-revenue` 同時吃 `start_month` 與 `start_date`)。

**SDK 對策**:對外統一 `start=` / `end=`,查表轉譯;該支無日期參數時傳入即 `UnsupportedParameterError`(不靜默忽略)。

---

## C. `as_of` 只有 17/82 支支援

且參數名本身分裂為 `as_of`(5)、`as_of_date`(21,含非 82 的 route)、`source_as_of_date`(3)。

**影響**:point-in-time 是 TWMD 的核心差異化,但目前八成的資料集無法在 server 端做 as_of 過濾。

**SDK 對策**:三態語義(`server` 17 / `client` 53 / `client_unverified` 5 / `unsupported` 7)。client 端過濾遇上 `limit` 截斷時會發 `TruncatedPointInTimeWarning`——這是 client 端補位無法完全消除的正確性風險,**只有 server 端支援 as_of 才能根治**。

**建議優先序**:先補基本面與事件類(`income_statement`、`balance_sheet`、`cash_flow_statement`、`financial_ratios`、`monthly_revenue`、`dividends`、`corporate_actions`),因為這幾支正是回測最容易產生未來函數的地方。

---

## D. `include_data_gaps` 只有 22/82 支支援

其餘 60 支無法從 server 取得缺口資訊。

**SDK 對策**:日頻且有實體參數者以 `trading_calendar` 在本地推算缺口(標 `gaps_source="client_derived"`),其餘標 `unknown`。本地推算無法區分「來源沒發布」與「本表沒載入」,**這個區分只有 server 端知道**。

---

## E. 分頁:`offset` 只有 9/82 支支援

其餘 73 支只有 `limit`(上限 5000)。打滿即截斷,且回應中**沒有欄位表明「還有更多」**。

**影響**:使用者無法分辨「這支資料就這麼多」與「被截斷了」。

**SDK 對策**:`limit` 打滿即標 `truncated=True` 並警告。但這是推測,不是 server 告知的事實 —— 正確解法是回應帶 `has_more` / `next_offset`。

---

## F. 回應 envelope 至少 4 種形狀,列陣列的 key 有 3 種

| 樣本 | 列的 key | 其他頂層欄位 |
|---|---|---|
| `twse_daily_price` / `tpex_daily_price` | `rows` | `count`, `data_as_of`, `source_role`, `lineage`, `meta` |
| `monthly_revenue` | `rows` | `count`(無 lineage、無 data_as_of) |
| `index_constituents` | `items` | `dataset_id`, `row_count`, `held_policy` |
| `market_index` | `data` | `data_count`, `dataset_id`, `envelope`, `known_gaps`, `quality`, `warnings`, `request_context` |

計數欄位也分裂為 `count` / `row_count` / `data_count`;資料集識別分裂為 `dataset` / `dataset_id`。

**SDK 對策**:依序嘗試 `rows` → `items` → `data` → `results`;計數同理。lineage / gaps / warnings 缺席時一律標 `unknown`,不推測。

---

## G. route 名與 dataset_key 不一致(6 支)

| dataset_key | 實際 route |
|---|---|
| `financial_ratios` | `/v2/datasets/financial-metrics` |
| `margin_short_total` | `/v2/datasets/total-margin-short` |
| `industry_index` | `/v2/datasets/index-classification` |
| `issuer_profiles` | `/v2/datasets/issuer-profile` |
| `interest_rate_snapshots` | `/v2/datasets/interest-rate-snapshot` |
| `taifex_final_settlement` | `/v2/datasets/futures-final-settlement` |

`financial_ratios` 的 describe 本身有註明這件事,其餘幾支沒有。

**SDK 對策**:方法名一律用 `dataset_key`,route 由 registry 查表;CI 每日 diff openapi,route 改名會被偵測到。

---

## H. 資料集口徑三個數字對不起來

| 來源 | 數字 |
|---|---|
| `GET /v2/datasets` 註冊表 | 125(active 105 / partial 9 / planned 7 / retired 2 / private_beta 1 / deprecated 1) |
| OpenAPI 掛載的 dataset route | 119 |
| MCP `list_datasets`(sellable + queryable) | 82 |

**SDK 對策**:以 82 為出貨範圍,並在文件明寫這是「可售集合」而非全部註冊項目。

---

## I. `403 temporarily_blocked` 的觸發門檻未文件化

4 併發掃 82 支即觸發,錯誤體只有 `{"error":"temporarily_blocked"}`,**沒有 `Retry-After`、沒有配額資訊、沒有說明要等多久**。

**影響**:使用者第一次跑批次就會撞到,而且會誤判成權限問題(403 通常讀作 forbidden)。

**SDK 對策**:預設 `max_concurrency=2` + 指數退避 + jitter,錯誤訊息明講「這是速率限制,不是權限不足」。

**建議**:回應加上 `Retry-After` 與剩餘配額;或把速率限制改回 429(語義正確)。

---

## J. knowledge 欄位宣告了但實際為 null

`monthly_revenue` 的 `announcement_date`、`source_publish_date` 在 2026-08-12 對 2330 的免 key 查詢中皆為 null,而該資料集的 PIT 註記正說明「回測應以公告日對齊」。

另有 5 支的 `knowledge_time_field` 宣告值不在 `/v2/datasets/{key}/schema` 的欄位清單中(見 `datasets_82.csv` 的 `as_of_mode=client_unverified`)。

**影響**:PIT 對齊在這幾支上目前無法真正執行。

**SDK 對策**:執行期檢查該欄是否存在且非全 null,否則發 `PITDataMissingWarning` / raise `PointInTimeUnavailable`,不假裝通過。
