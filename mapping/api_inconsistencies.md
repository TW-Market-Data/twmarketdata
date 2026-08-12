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

## C. `as_of` 只有 17/82 支的 route 有這個參數

且參數名本身分裂為 `as_of`、`as_of_date`、`source_as_of_date`。

**影響**:point-in-time 是 TWMD 的核心差異化,但目前八成的資料集無法在 server 端做 as_of 過濾。

**SDK 對策**:五態語義 —— `server` 16 / `client` 45 / `client_unsafe` 8 / `client_unverified` 5 / `unsupported` 8。
(17 支有參數但只有 16 支走 `server`:`subsidiary_investment` 的 route 接受 `as_of_date`,而 describe 宣告它無知識軸且 `point_in_time_safe=false`,SDK 依語義拒絕。)

client 端過濾有兩個**無法在 client 側根治**的風險:

1. 先被 `limit` 截斷再本地過濾,會把「其實有資料」誤判成「那天還沒有」→ 發 `TruncatedPointInTimeWarning`。
2. `point_in_time_safe=false` 的 8 支,宣告的欄位其實是期別/生效日/觀察日,本地過濾等於引入未來函數 → SDK 預設拒絕(`client_unsafe`)。

**兩者都只有 server 端支援 as_of 才能根治。**

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

---

## K. 三支標示 `tier=free` 的資料集實際回 401

82 支全數以免 key、每 4 秒一發的低速率探測(2026-08-12,零封鎖):19 支回 200、63 支回 401。其中**標示為 free 卻回 401** 的有三支:

| dataset_key | registry_status | 探測結果 |
|---|---|---|
| `valuation_data` | active | 401 missing_api_key |
| `issuer_profiles` | active | 401 missing_api_key |
| `industry_index` | planned | 401 missing_api_key |

`industry_index` 是 `planned`,401 合理。另兩支是 `active` + `free`,tier 宣告與實際門檻對不上。

**影響**:`tier` 欄位無法單獨用來判斷「這支免 key 能不能跑」,SDK 的免費層範例只能以實測結果為準。

**SDK 對策**:`datasets_82.csv` 另立 `free_tier_probe_2026_08_12` 欄記錄實測,README 範例只綁實測可跑的 16 支;`tier` 僅作為錯誤訊息裡的「需要哪個方案」提示。

---

## L. 已退役的 gateway 仍是既有 0.1.0 SDK 的預設 base_url

`packages/python-sdk` 的 0.1.0 預設 `base_url="https://twmarketdata.com"`,該路徑現已回:

```
HTTP/2 410
{"error":{"code":"endpoint_retired","message":"This gateway is retired. Call the TW Market Data API
directly at https://api.twmarketdata.com/v2/datasets/... with your sk_live_ key in the X-API-Key
header. Keys issued in the dashboard authenticate there, never here."}}
```

**注意兩個 host 的錯誤體形狀不同**:

| host | 錯誤形狀 |
|---|---|
| `twmarketdata.com`(已退役) | `{"error": {"code": ..., "message": ...}}` — error 是物件 |
| `api.twmarketdata.com`(現行) | `{"error": "missing_api_key", "message": ...}` — error 是字串 |

website `main` 上的 0.1.0 錯誤解析是照**前者**寫的,打現行 API 時 `_extract_error_code` / `_extract_error_message` 一律回 `None`,錯誤訊息退化成 `Request failed with status 401.`,遺失 server 給的中文說明。

**但這件事已經有人修了,只是沒合併**:分支 `fix/friction01-sdk-error-contract`(commit `53874b2`,worktree 在 `_wt/friction01-sdk`)已支援扁平 `{error, message}`,並依 FRICTION-01 R2 重新分類:402 `not_entitled_for_dataset` / `dataset_not_entitled` / `commercial_use_not_allowed`、403 改為「已認證但被禁止」(`api_key_not_active`、`mcp_not_in_plan`、`plan_not_entitled`、`dataset_not_allowed`、`api_key_revoked`)、429 併入 `daily_quota_exceeded` / `monthly_quota_exceeded`。

`git branch --contains 53874b2` 顯示**只在該分支上,未進 main**。而且 **base_url 在該分支也沒改**,仍指向已退役的 gateway —— 修好的錯誤解析目前打不到任何活著的端點。

**建議**:
1. 把 `fix/friction01-sdk-error-contract` 合併(或至少把它的錯誤碼分類搬進新 SDK 當基準,新 SDK 已這麼做)。
2. 現行 API 與 gateway 統一成同一種錯誤形狀,二選一即可 —— 重點是**同一個產品只有一種錯誤形狀**。
3. 現行 API 補上 `endpoint_retired` 之外的扁平/巢狀一致性,讓 client 不必兩種都解。

---

## M. `/v2/datasets/{key}/schema` 的欄位名 ≠ 回應實際欄位名

實作 SDK 的 PIT 時發現:`twse_daily_price` 的 describe 宣告 `knowledge_time_field=trade_date`,`/schema` 端點也列出 `trade_date`,但**實際回應投影出來的欄位叫 `date`**。

```
GET /v2/datasets/twse-daily-price?symbol=2330&limit=1
{"rows":[{"symbol":"2330","date":"2026-08-10","open":2390.0, ...}]}
                                  ^^^^ 不是 trade_date
```

`monthly_revenue` 同樣:宣告 `as_of_date`,回應實際給的是 `month` / `revenue_month`。

**影響(嚴重)**:任何照 schema/describe 做 point-in-time 對齊的下游,都會找不到知識欄位。SDK 若因此靜默不過濾,使用者會拿到一份「看起來有 as_of 其實沒有」的資料 —— 正是 PIT 差異化最不能出的錯。

**SDK 對策**:
1. 只針對**已實測確認為同義**的欄位建立別名(目前只有 `trade_date` ↔ `date`),絕不做「看起來很像」的猜測。`as_of_date` **不**對應到 `month`/`revenue_month`,因為期別不是知道日。
2. 解析不到宣告欄位時,發 `PITDataMissingWarning` 並**明確區分「欄位不存在」與「欄位存在但全為 null」**,兩者訊息不同。
3. 兩種情況都 `as_of_applied=False`,不假裝過濾成功。

**建議**:讓 `/schema` 與 describe 反映**投影後**的欄位名(或在回應中同時保留 `trade_date` 別名)。目前的落差讓「照文件寫」必然出錯。

---

## N. `price-enhanced` 的 contract 宣告 OHLCV,但 schema 與實際回應都是調整因子

由左下實測回報:`price-enhanced` 的 contract 宣告 OHLCV(`close` / `open` / `high` / `low` / `volume` / `return_1d`…),其中 `close` 是 required,但實際服務的是調整因子欄組:

```
ticker, market, trade_date, event_type, factor, pre_event_close, reference_price
```

`close` 這個 required 欄位**不會出現**。

**本 repo 的交叉驗證(2026-08-12)**:

| 來源 | 說了什麼 |
|---|---|
| `GET /v2/datasets/price_enhanced/schema` | `id, ticker, trade_date, event_type, factor, pre_event_close, reference_price, market, provider, source_role, source_authority, source_family, source_hash, lineage, created_at` —— **調整因子那組,沒有 OHLCV** |
| `openapi.json` 的 200 response schema | 未定義欄位(`type: object`、`additionalProperties: true`),**沒有宣告任何欄位** |
| `llms-full.txt` | **沒有** `price_enhanced` 這一筆 |
| `datasets_82.csv` 的 `columns` 欄 | 與 `/schema` 一致,即調整因子那組 |

也就是說:**`datasets_82.csv` 沒有抄到錯的 OHLCV,不需要修正**。OHLCV 的宣稱不存在於本 repo 引用的任何一份 API 證據裡,因此那份 contract 是另一個獨立來源(dataset contract / 資料集頁 / 內部契約登錄),我這側無法直接驗證(該資料集 tier=starter,免 key 回 401),依左下回報記錄於此。

**與第 M 項的關係(方向相反,同一類病)**:

| | 宣告 | 實際回應 |
|---|---|---|
| M | schema / describe 說 `trade_date` | 回 `date` |
| N | contract 說 OHLCV(含 required `close`) | 回調整因子欄組(schema 也是這組) |

M 是 schema 與投影不一致;N 是 contract 與 schema+投影**兩者都**不一致 —— 亦即 contract 是三者之中唯一錯的那個。

**影響**:任何照 contract 產生型別、做欄位驗證或寫必填檢查的下游,對 `price-enhanced` 都會失敗或誤判。SDK 這側不受影響(欄位取自 `/schema` 而非 contract),但 `close` required 的宣告會讓契約測試假失敗。

**建議**:以實際投影為準修正 contract(或明確標示該 contract 已作廢),並在 API 一致性工單裡把「contract / schema / 實際回應」三者對齊列為一個檢查項 —— 目前三份宣告可以互相矛盾而沒有任何機制會發現。

---

## O. 同一個 envelope 家族裡,`envelope` 有時是 metadata、有時(據報)裝著列

左上回報:`price-enhanced` 的列可能落在 `body["envelope"]["data"]`,不在頂層。

**本 repo 對免 key 可達的同家族資料集實測(2026-08-12)**:

| 資料集 | 列在哪 | `envelope` 這個 key 是什麼 |
|---|---|---|
| `index-constituents` | 頂層 `data` | **dict**,內容是 `{dataset_id, scope, row_count}` —— metadata,不是列 |
| `stock-delisting-lifecycle` | 頂層 `data` | **dict**,同上 |
| `market-index` | 頂層 `items` | **不存在這個 key** |
| `price-enhanced` | 據報在 `envelope.data` | 無法自行驗證(tier=starter,免 key 回 401) |

也就是說 **`envelope` 這個名字在同一個家族裡至少有兩種意思**:大多數情況是 metadata 容器,而據報在 `price-enhanced` 是列容器。單看欄名無法判斷。

**這個坑特別惡劣的地方**:同一批回應的 `request_context`、`quality`、`lineage` 底下**都有自己的陣列**——實測分別是 `snapshot_dates_in_page`、`indices_present`、`source_families`。任何「往下找第一個 list 就當成資料」的解析器,會把這些 metadata 陣列當成資料列回給使用者。**回錯資料比回空更糟。**

**SDK 對策(已實作)**:

1. 先試頂層的 `rows` / `items` / `data` / `results` / `records`。
2. 找不到才往下**一層**,而且只進白名單容器(`envelope` / `payload` / `body` / `response` / `result`),並且只認上述那幾個列 key。
3. `lineage` / `quality` / `request_context` / `meta` / `error` / `warnings` / `known_gaps` **永不下探**。
4. 巢狀候選必須**整個陣列都是物件**才採用 —— 純量陣列(日期清單、代號清單)一律拒絕。
5. 命中巢狀時 `Meta.row_key` 記成 `"envelope.data"`,使用者看得到列是從哪裡取出來的。

`price-enhanced` 本身我無法驗證(需要 key),上述處理是依左下/左上回報做的防禦性實作,拿到測試 key 後要實測確認。

**建議**:同一家族的 envelope 統一 —— `envelope` 要嘛永遠是 metadata、要嘛永遠是列容器,不要兩種都是。這跟第 F 項(列的 key 有三種)是同一件事的延伸:**光是「列在哪裡」目前就有 4 種以上的答案**。

---

## P. `price-enhanced` live 確認(A 項與 O 項的實例),以及「未知參數」處理的真實規則

左上 live 確認兩件事,兩件都落在既有條目底下:

| 確認 | 同類條目 | SDK 現況 |
|---|---|---|
| 列在 `body["envelope"]["data"]`,不在頂層 | **O** | 已接住(白名單容器下探,`Meta.row_key` 記為 `envelope.data`) |
| 吃 `ticker` 不吃 `symbol`,傳 `symbol` 回 422 | **A** | 已接住(registry 記錄該 route 的實體參數為 `ticker`,SDK 對外統一 `ticker=` 再翻譯) |

`price-enhanced` 是 starter tier,本 repo 無法免 key 直接驗證這兩點;registry 的 `ticker` 來自 OpenAPI 宣告(該 route 只宣告 `ticker`,沒有 `symbol`),與左上的 live 結果一致。

### 順帶釐清:422 的真正成因不是「symbol 被拒絕」

免 key 實測(2026-08-12):

| 請求 | 結果 |
|---|---|
| `twse-daily-price?symbol=2330` | 200,1 列 |
| `twse-daily-price?ticker=2330` | **422** `{"error":"validation_error","message":"symbol: Field required"}` |
| `twse-daily-price?symbol=2330&utter_nonsense=1` | **200**,1 列 —— 未知參數被靜默忽略 |
| `index-constituents?symbol=2330` | **200** —— 該 route 無必填參數,`symbol` 被忽略 |
| `trading-calendar?symbol=2330` | **200** —— 同上 |

OpenAPI 的必填宣告佐證:`price-enhanced` 必填 `ticker`、`twse-daily-price` 必填 `symbol`、`index-constituents` 無必填。

所以真實規則是:**未知參數一律被靜默忽略;422 只在「必填參數缺席」時出現。** 傳 `symbol` 給 `price-enhanced` 之所以 422,是因為必填的 `ticker` 沒給,而不是因為 `symbol` 被拒絕。

**這一點很重要,因為靜默忽略是有害的**:對**沒有必填參數**的 route(`index-constituents`、`trading-calendar` 等,82 支裡有 30 支無實體參數),傳錯參數名會**安靜地回全量資料**,看起來像是過濾過的結果。使用者不會收到任何訊號。

**SDK 對策**:傳了該資料集不支援的參數一律 `UnsupportedParameterError`,在送出請求**之前**擋下。這正是「寧可報錯也不要默默忽略」那條規則要防的情境 —— server 這側目前不會告訴你。

**建議**:未知查詢參數改為 422(或至少在回應的 `warnings` 裡列出被忽略的參數名),讓「打錯參數名」不再靜默地變成「查詢了全部」。

---

## Q. `limit` 上限有五種,而且**宣告值不等於實際執行值**

以受限測試 key 對 82 支實測(2026-08-12)。OpenAPI 對每支 route 宣告的 `limit` `maximum`:

| 宣告上限 | 支數 |
|---|---|
| 500 | 30 |
| 5000 | 26 |
| 1000 | 24 |
| 2000 | 1(`trading_calendar`) |
| 100 | 1(`company_news`) |

**56/82 不是 5000。** 任何寫死 5000 的 client,對這 56 支不是被 422 拒絕就是被靜默截斷。

### 更嚴重:宣告與執行不一致

`margin_system_stats` 的 OpenAPI 宣告 `maximum: 5000`,實際:

```
limit=5000 → 422 {"error":"validation_error","message":"limit: Input should be less than or equal to 1000"}
limit=2000 → 422 同上
limit=1000 → 200
```

**照文件寫必然失敗。** 已知至少 `margin_system_stats` 一支;其餘宣告 5000 的 25 支尚未逐支驗證。

**SDK 對策**:
1. registry 記錄每支的宣告上限,送出前先 clamp;使用者明確要求超過就 clamp 並警告(不靜默縮小)。
2. 仍收到 422 時,**從 server 的錯誤訊息解析出真正的上限並重試一次**,並發 `TruncatedResultWarning` 說明「規格宣告 X、實際只收 Y」。這是被迫的自我修正,不是設計美感。

**建議**:讓 OpenAPI 的 `maximum` 與實際 validator 同源產生。目前兩者可以各說各話而沒有任何機制會發現。

---

## R. `422` 與 `400` 先前無型別;`missing_required_filter` 出現在 registry 說無必填的 route 上

- `market_breadth` 回 `400 {"error":"missing_required_filter","message":"Missing required filter"}`,但 OpenAPI 對該 route **沒有宣告任何必填參數**,且訊息**沒說缺哪一個**。
- `422 validation_error` 先前落到通用錯誤類別。

**SDK 對策**:新增 `ValidationError`(400/422/`validation_error`/`missing_required_filter`),並保留 server 原文 —— 因為只有 server 的訊息會點名欄位(如 `limit: Input should be...`)。0.1.0 的 `TwmdValidationError` 現在是它的別名。

**建議**:必填參數要在 OpenAPI 宣告;錯誤訊息要指名缺哪一個。

---

## S. `500 Internal Server Error` 間歇出現,且回應是純文字不是 JSON

同一個請求會時好時壞:

```
price-enhanced?ticker=2330&limit=3  →  200(一次)
price-enhanced?ticker=2330&limit=3  →  500(隨後連續三次,間隔 5 秒)
price-enhanced?ticker=2330&limit=5  →  500
company-news?ticker=2330&limit=3    →  500(但 limit=5 錄製時是 200)
capital-formation-events?limit=3    →  500(但 limit=5 錄製時是 200 且有 5 列)
```

而且 500 的 body 是純文字 `Internal Server Error`,**不是 JSON**,沒有 `request_id`,無法追蹤。

**SDK 對策**:5xx 已納入退避重試;非 JSON body 包成 `{"raw": ...}` 不會炸掉解析。

**建議**:500 也回 JSON 錯誤體並帶 `request_id`,否則使用者回報問題時我們無從追查。間歇性本身需要另外查(三支都與 `envelope.data` 形狀相關,可能同源)。

---

## T. `X-TWMD-*` 回應 header 不存在(0.1.0 的 `ResponseMeta` 因此是空的)

0.1.0 的 `ResponseMeta` 讀 `X-TWMD-Dry-Run`、`X-TWMD-Credits-Cost`、`X-TWMD-Credits-Charged`、`X-TWMD-Plan`。帶 key 實測(200 回應):

```
HTTP/2 200
x-render-origin-server: uvicorn
x-request-id: req_6f95b7d164e248f1
```

**那四個 header 一個都沒有**,所以 0.1.0 的 `ResponseMeta` 五個欄位有四個永遠是 `None`。

**SDK 對策**:0.2.0 不依賴這些 header;方案資訊改由回應 body 的 `plan_id` 取得(實測 `price_enhanced` 的 body 有 `"plan_id": "max"`)。

---

## U. tier 不是單一階梯:`max` 方案不含 `developer` 級資料集

以 **max tier** 的 key 實測,仍有 10 支回 402 `not_entitled_for_dataset`,全部是 `developer` 或 `enterprise` 級(`block_trade_daily`、`etf_holdings`、`interest_rate_snapshots`、`subsidiary_investment`、`tax_business_registration`、`esg_ghg_carbon_disclosure`、`governance_t187ap33_l`、`macro_worldbank`、`market_overview_snapshots`、`macro_global`)。

也就是說 `free < starter < pro < max` 之外,`developer` / `enterprise` 是**旁支**而非更高階。

**影響**:文件若讓人以為 tier 是線性階梯,買 max 的使用者會預期拿到 developer 級資料。

**SDK 對策**:`TierRequiredError` 保留 server 原文(訊息本身有講需要哪個方案);不自行推論階梯順序。

**建議**:定價頁與 API 文件明確說明 developer/enterprise 不包含在 max 內。

---

## V. entitlement 是 per-key 的,tier 標籤無法預測(修訂 2026-08-12)

2026-08-12 核發一把標示為 **developer / 6 datasets** 的 key。對三支 `developer` 級資料集實測:

| 資料集 | tier | max key | developer key |
|---|---|---|---|
| `etf_holdings` | developer | 402 | **402** |
| `interest_rate_snapshots` | developer | 402 | **402** |
| `block_trade_daily` | developer | 402 | **402** |

錯誤訊息是 `not_entitled_for_dataset`,內文寫「**developer 方案涵蓋它**」—— 也就是說,**一把標示為 developer 的 key,拿到的錯誤訊息叫它去買 developer 方案**。

同一把 key 可正常讀取 `company_news`(pro)、`valuation_core_daily`(pro)、`price_move_context`(starter)。

**後續(同日)**:另一把新鑄的 developer 拋棄金鑰對 `/v2/datasets/etf-holdings` **回 200 + 真資料**。兩件事同時成立,不互相矛盾:

| key | `etf-holdings` |
|---|---|
| max(受限測試 key) | 402 `not_entitled_for_dataset` |
| 標示 developer / 6 datasets 的那把 | 402(重現於 2026-08-12,`x-request-id: req_45c82a1f872e4e3d`) |
| 新鑄的 developer 拋棄金鑰 | **200 + 真資料** |

所以本項的結論要收斂成:**entitlement 綁在個別 key 上,而 key 上的 tier 標籤不保證對應的 entitlement 已經寫入。** 原先的標題(「developer 級 key 拿不到 developer 級資料集」)講得太廣,已修正 —— 正確描述是「**曾有兩把 key,其中一把標示為 developer,實際 entitlement 不含該 tier 的資料集**」。

**影響**:`twmd.capabilities(...)["tier"]` 只能當提示,不能當「這把 key 能不能讀」的判斷依據 —— 與第 K 項(標 free 卻回 401)是同一個病在付費層的版本。

**SDK 對策**:不從 tier 推論可讀性(這點不因上面的修訂而改變 —— 反而更成立);`TierRequiredError` 保留 server 原文。

### 第三次量測(新鑄的 developer 拋棄金鑰,plan=developer / 6 datasets / quota 2000 / 24h)

重錄先前 10 支回 402 的資料集:

| 結果 | 資料集 |
|---|---|
| **200** (6 支,正好等於方案宣告的 6 datasets) | `etf_holdings`、`block_trade_daily`、`subsidiary_investment`、`esg_ghg_carbon_disclosure`、`governance_t187ap33_l`、`market_overview_snapshots` |
| **403 `commercial_use_not_allowed`** (3 支) | `interest_rate_snapshots`、`tax_business_registration`、`macro_worldbank` |
| **402 `not_entitled_for_dataset`** (1 支) | `macro_global`(enterprise 級,合理) |

**403 的錯誤碼與情境對不上。** 完整回應:

```
GET /v2/datasets/interest-rate-snapshot?limit=2      x-request-id: req_945946cacc15454e
HTTP/2 403
{"error": "commercial_use_not_allowed",
 "message": "Developer 僅限個人開發與測試使用,不可用於商業產品或對外服務。
             升級至 Pro 或 Enterprise 以用於商業產品與正式環境。"}
```

這把 key 的用途**正是**個人開發與測試(錄 SDK 測試用 cassette),而且同一把 key 讀另外 6 支 developer 級資料集都是 200。所以實際成因不是商業用途,而是**該資料集不在這把 key 的 6 支 allow-list 內** —— 但回的錯誤碼講的是授權條款,不是 allow-list。

**影響**:使用者照訊息去升級 Pro 也解決不了問題,因為問題不在方案等級。

**建議**:allow-list 未命中要回自己的錯誤碼(或 402 `not_entitled_for_dataset`),訊息列出這把 key 實際涵蓋的資料集,而不是引用商業使用條款。

**SDK 對策**:`commercial_use_not_allowed` 已在 `_ENTITLEMENT_CODES` 內,402/403 兩種形狀都對映到 `TierRequiredError`,且保留 server 原文 —— 呼叫端不必分辨是哪一種。

**建議**:錯誤訊息應指出**這把 key 目前的 entitlement 清單**,而不是重述資料集的 tier 標籤 —— 現在的訊息會讓已經買了 developer 的人以為自己沒買。
