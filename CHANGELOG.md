# Changelog

## 0.6.2 — 未發布

### Added

- **`twmd schema`** —— 這支 CLI 的機器可讀自述(預設 `--format json`)。

  `datasets` 說有哪些資料集,`describe` 說**一個資料集**的參數與 as_of 語意,
  而**沒有任何一支說這個工具本身**有哪些指令、吃什麼參數、回哪些 exit code。
  agent 目前只能去 parse `--help` 的人類文字,而排版一改猜法就壞 ——
  壞的方式還是安靜的:參數解析出空值,不會報錯。

  ⚠️ **沒有手寫第二份 schema。** 它走 `build_parser()` 的 argparse 結構把參數
  **讀出來**。手寫的那份會漂,而漂掉時 CLI 和 schema **兩邊都不會變紅** ——
  照著一份過期說明組出來的指令,錯得無聲無息。測試臨時往 parser 塞一個旗標,
  要求 schema 看得到它。

  ⚠️ **沒有 `point_in_time_safe` 布林。** PIT 對不對取決於這次呼叫有沒有給
  `--as-of`,以及那個資料集的知識時間欄位 —— 那是 per-dataset 的事實,
  `describe` 已經在回。一個工具層的布林只會**蓋掉**它。給的是機制加上省略的後果。

  ⚠️ **`read_only` 是算出來的**,不是宣告的。一個寫死的 `true` 在有人加了寫入
  指令的那天不會改變 —— 而那正是它唯一該改變的那天。

  預設 `json` 而不是人類表格:這支指令的讀者是程式。不需要 API key ——
  自述是**接上去之前**要讀的東西。

---

> ⚠️ 以下 **0.6.0 / 0.6.1 兩則是事後補記的**。它們發版時沒有寫 changelog,
> 也沒有打 tag,所以內容是 2026-08-28 從 **PyPI 上已發布的 sdist** 逐檔比對
> 重建的 —— 不是憑記憶寫的。逐檔差異列在每一則的開頭。

## 0.6.1 — 2026-08-27

> 重建依據:相對 0.6.0 新增 `twmd/agent_contract.py`、`twmd/engines.py`;
> 內容改動 `twmd/__init__.py`、`twmd/_cli.py`。

### Added

- **`twmd/agent_contract.py`** —— agent 輸出契約。exit code 逐一凍結成數值、
  機器格式下的錯誤信封、以及 CSV **刻意不給**信封的理由。

  ⚠️ 重新編號 exit code **不會讓任何測試變紅**,也不會讓任何人的腳本報錯 ——
  它只會讓別人腳本裡的 `if rc == 4:` 開始指向別的意思。所以是逐一釘住數值。

  ⚠️ CSV 失敗時 stdout 刻意留空:一列 CSV 錯誤和一列資料長得一模一樣,
  消費端的 `csv.reader` 沒有辦法分辨 —— 那比空的 stdout 危險得多。

- **`twmd/engines.py`** —— `to_polars()` / `to_arrow()`,以及 `--format parquet`。

  ⚠️ `to_polars()` 回**兩個值** `(frame, pit)`:Polars 沒有 `attrs` 這種使用者層
  掛載點,硬塞 PIT 會變成一個**假欄位**,而假欄位會被聚合、被 join、被寫進輸出。

  ⚠️ `to_arrow()` 把 PIT 嵌進 **Arrow schema**,所以它跟著檔案離開這個行程。
  實測(pandas 2.3.3)`.attrs` 撐得過 parquet 往返與 groupby/concat,**但 merge
  會掉** —— 而合併資料集正是回測管線最常做的事,掉了之後那份 DataFrame 和一份
  沒有 as_of 的看起來一模一樣。

  ⚠️ `--format parquet` **`--out` 必填,而且在取資料之前就檢查**:parquet 是
  二進位,寫進 stdout 會弄壞終端機;而檢查放在 fetch 之後的話,一個忘了 `--out`
  的呼叫會先花掉一次 API 請求(以及使用者的額度)才說參數不對。

### Fixed

- **`twmd --version` 改讀已安裝套件的 metadata**(`twmd/__init__.py`)。

  硬編碼的版本常數**必然**會漂:發 0.6.0 時 pyproject 更新了、那一行沒有,
  於是 `--version` 對外說 0.5.0 而使用者裝到的是 0.6.0。

## 0.6.0 — 2026-08-27

> 重建依據:相對 0.5.0 新增 `twmd/_ask_guard.py`,無既有模組內容改動。

### Added

- **`twmd/_ask_guard.py`** —— `ask` 路徑的唯讀護欄與 PIT 釘選。

  唯讀工具白名單、禁止的執行類名稱(`eval` / `exec` / `compile` / `__import__`),
  以及 `pin_as_of()`:省略 `--as-of` 時**注入並回報**,而不是安靜地拿最新修訂值。

  ⚠️ 知識軸判定委派給 `pit.resolve_mode`,不在這裡另寫一套 —— 兩套判定會在
  某天對同一個資料集給不同答案。

## 0.5.0 — 2026-08-26

CLI Phase 2。**SDK 的行為仍然沒有任何改變**,新增的全在命令列這一層。

### Added

- **`twmd ask "問句"`** —— 路由到既有的 MCP `ask` 工具。

  ⚠️ **CLI 不做任何問句推斷。** 實測 `/v2/ask` 是 404、`/v2/search` 是文件搜尋
  (查「月營收」回 0 筆),所以「路由到既有 ask」只有一條誠實的路:呼叫那個
  MCP 工具。在 CLI 裡自己寫「問句 → 資料集」的猜測,會和 MCP 那邊的路由分岔 ——
  同一個問題兩個答案,而沒有人會發現。

  **來源一定印**(走 stderr);沒有來源時明講 `unsourced` —— 一個沒有來源的答案,
  和一個編出來的答案在讀者眼裡一樣。省略 `--as-of` **不會**幫你填今天,
  只會在 stderr 講明拿到的是最新修訂值。

  需要 Pro 以上方案(`tools/call` 不在免金鑰白名單)。免金鑰的 5 檔範例仍走
  `twmd get`,不受影響。

- **`twmd tui`** —— Textual 全螢幕介面:資料集 / 結果表 / **來源與 as_of** 三面板。

  ⚠️ 第三個面板不是裝飾。一個只顯示數字的終端機介面會讓人忘記那些數字有時點和
  來源,而那正是這個產品和一張截圖的差別。

  ⚠️ **只在真人終端機。** 被 pipe、被 CI 跑、被 agent 呼叫時進 TUI,結果不是
  「介面比較醜」——Textual 會接管終端機並等一個永遠不會來的按鍵,程序就掛在那裡。
  沒裝 textual 不是壞掉,是退回引導選單並說明原因。

- **`twmd 2330`** —— 代號捷徑:行情 + 月營收 + 「想看什麼」下一步。

  ⚠️ 判斷刻意窄(4–5 碼數字,可帶一個字尾字母:`2330` / `0050` / `00631L`)。
  把不認得的字串都當股號,會讓 `twmd datsets` 這種打錯變成「查不到這檔股票」,
  而你要找的是自己打錯了指令。

  一段資料集拿不到時,其他照出並**說出**哪一段沒拿到 —— 安靜地少一段,
  讀起來像那段不存在。

- **撞牆時的升級引導**:方案不足時明講「這是方案問題,不是設定問題」+ 升級連結,
  並說明**升級用同一個 email、下一次呼叫自動生效(約一分鐘內)、不需要重連**。
  沒有金鑰則是設定問題,**不會**把你送去付費頁。

### Fixed

- **`twmd <ticker> --format json|csv` 送出兩份文件,解析不了。** 每個資料集各印
  一次,於是 JSON 是兩個接在一起的陣列、CSV 是兩份各自帶表頭。機器格式現在合成
  **一份**,每列多一個 `dataset` 欄位標明來源。人看的表格仍分段顯示。
- **`00631L` 這類代號認不出來。** 第一版的規則是「前 4 碼數字 + 其餘皆字母」,
  而 5 碼 ETF 帶字尾時第 5 碼還是數字。

### 鐵律(不變)

無色、無 banner、無 TUI 的條件:`--format json|csv`、stdout 不是 TTY、
`NO_COLOR` 有設、`TERM=dumb`。零參數 + 被 pipe 印 help,**不進任何互動介面**。
UI 套件(rich / questionary / textual)全部走 `pip install twmarketdata[cli]`,
核心 `import twmd` 仍然只依賴 `requests`。

## 0.4.0 — 2026-08-25

CLI 的第一階段「人人好用」。**SDK 的行為沒有任何改變**,新增的全在呈現層。

### Added

- **彩色表格**(`twmd get` / `twmd datasets`):數字右對齊、漲跌欄負紅正綠、
  表頭粗體,下方一行帶資料集、涵蓋範圍、`as_of` 與 verify 連結。

  ⚠️ 顏色只給**帶正負號意義**的欄位(yoy / mom / 漲跌 / 報酬 …)。把股價或
  成交量塗成綠色沒有意義 —— 它們永遠是正的,只會把真正有意義的漲跌顏色稀釋掉。

- **TWMD banner + 互動模式**:`twmd` 不帶參數 → banner + 選單(分類 → 資料集 →
  股號)→ 彩色結果 + 來源 + 下一步。全程不用打任何 flag。
  banner 是靜態一次印完的:會重繪的 banner 在 `script`、慢速 SSH 或被記錄的
  終端機裡會變成一團控制碼。

- **友善錯誤**:打錯資料集名字會給猜測(`monthly-revenue` → `monthly_revenue`,
  dash/underscore 是最常見的一種),而且**只在夠接近時才猜** —— 對每個輸入都
  硬湊一個建議,會在你真的打錯時把你帶去別的地方。
  沒金鑰和方案不夠**分開講**:前者是設定問題(設好環境變數就行),後者是方案
  問題(金鑰是好的,附升級連結,而升級用同一個 email、不用重連)。

- **`[cli]` 可選附加**:`pip install twmarketdata[cli]` 才裝 rich/questionary。
  核心 `import twmd` 仍然只靠 requests —— 一個只想取數的人不該為了別人的
  彩色表格被迫裝一堆 UI 套件。**沒裝不是壞掉**,是退回純文字。

### 鐵律:機器拿到的永遠乾淨

無色、無 banner 的條件(任一成立):`--format json` / `--format csv`、
stdout 不是 TTY(被 pipe 或導向檔案)、`NO_COLOR` 有設、`TERM=dumb`。

`NO_COLOR` **有設就算數,不看值** —— 檢查值等於發明一個別人不知道的規則。

⚠️ 被 pipe 時**一欄都不會少**:彩色表格為了可讀性會顯示前 7 欄(並印出
「showing 7 of 13 columns」),而 CSV / JSON / 純文字一律給完整欄位。
呈現層修剪的是呈現,不是資料。

零參數 + 被 pipe **不會**進互動選單 —— 那會永遠等一個不會來的輸入。改為印 help。

## 0.3.0 — 2026-08-25

新增一個命令列工具。SDK 的行為完全沒變 —— 沒有破壞性變更。

### Added

- **`twmd` 命令列**(`pip install twmarketdata` 之後就有):
  `datasets` / `describe` / `coverage` / `get` / `auth` / `version`。

      twmd datasets --free-only
      twmd describe monthly_revenue
      twmd get monthly_revenue --ticker 2330 --as-of 2024-06-30 --format csv

  它是既有 `Client` 與 registry 的**薄殼** —— 取數、分頁、PIT 過濾、缺口與
  錯誤分類全部走同一份程式碼。自己組 HTTP 請求的 CLI 會複製一份 PIT 語意,
  而兩份語意遲早會分歧;分歧那天兩邊看起來都正常。

  三件刻意的行為:

  1. **省略 `--as-of` 會在 stderr 講明**拿到的是最新修訂值 —— 對回測那是
     未來函數,而回應是 200,看起來完全正常。
  2. **缺口與截斷走 stderr,資料走 stdout。** 所以
     `twmd get … --format csv > out.csv` 的檔案是乾淨的 CSV,而你仍然看得到
     少了什麼。(SDK 用 `warnings` 表達這些,而 Python 預設同一個警告只印一次
     —— CLI 關掉了那個去重。)
  3. **exit code 分類**:3 auth、4 entitlement、5 unknown dataset、
     6 rate limited、7 invalid parameter、8 upstream。全部回 1 等於逼你去
     grep 錯誤訊息字串,而訊息是會改的。

  ⚠️ CLI **不需要 pandas**。它走 `Client.dataset()` 的無-pandas 路徑,所以
  安裝體積不變。

### Fixed

- **`project_urls` 的 Source 指向一個不存在的位址。**
  舊值 `github.com/twmarketdata/twmd-python-sdk` 的 organisation 和 repo
  都不存在(GitHub API 對兩者皆回 404),而 PyPI 專案頁把它顯示成可點的連結
  —— 要評估這個 SDK 的人第一個動作就會撞到 404。現在指向
  `github.com/TW-Market-Data/twmarketdata`。

## 0.2.1 — 2026-08-12

Recording-only release: the same client, verified against a much wider slice of
the paid API than 0.2.0 could reach.

### Changed

- **62 of the 63 paid-tier cassettes now record real data**, up from 52. The
  entitlement fix upstream cleared the `403 commercial_use_not_allowed`
  responses entirely, so `etf_holdings`, `interest_rate_snapshots`,
  `tax_business_registration` and `macro_worldbank` are recorded from live rows
  rather than from a refusal. The one remaining refusal is `macro_global`,
  which is enterprise tier and private beta — a developer key not reaching it is
  correct, not a defect.
- **Two routes require a filter the API spec does not declare**, and their 400
  does not say which one. The working combinations were measured and are now
  carried in the registry, so `ValidationError` names them instead of leaving
  you to guess:

      twmd.capabilities("interest_rate_snapshots")["required_filters"]
      # ['rate_family', 'rate_code']
      twmd.capabilities("market_breadth")["required_filters"]
      # ['market', 'date_from+date_to']

  The two routes want different things, and `date_from`+`date_to` satisfies one
  but not the other, so there is no rule to infer — only the two measured
  entries get a hint, and nothing is invented for the other 80.

### Fixed

- Nothing in the client itself. 0.2.0's behaviour is unchanged; this release
  exists because PyPI does not allow re-uploading a version.

## 0.2.0 — 2026-08-12

First release under Apache-2.0. 0.1.0 remains MIT; the relicence applies from
0.2.0 onward and was made by the copyright holder.

Same distribution (`twmarketdata`) and same import name (`twmd`), so
`pip install -U twmarketdata` is the whole upgrade. **Everything 0.1.0 exported
still resolves and still works**, now emitting `DeprecationWarning` naming the
replacement. See "Upgrading from 0.1.0" in the README.

### Added

- **All 82 sellable datasets get a named method**, generated from the live API's
  own registry so none can be silently missed. Plus `Client.dataset()` as a
  generic escape hatch and `twmd.capabilities(name)` so limits are discoverable
  without trial and error.
- **Uniform parameters.** The API spells the security identifier seven ways and
  date bounds five ways; the SDK takes `ticker=`, `start=`, `end=` everywhere
  and translates per route. Routes keyed by something that is not a stock
  ticker (13 of them — `issuer`, `cb_id`, `contract`, `index_code`) also accept
  their native name, so `issuer="…"` reads correctly instead of a stock code
  being sent as an issuer code.
- **Point-in-time with five states**, decided per dataset and visible in
  `capabilities()`: `server` (16), `client` (45), `client_unsafe` (8),
  `client_unverified` (5), `unsupported` (8). The last two categories *refuse*
  `as_of` rather than returning a frame that merely looks replayed.
- **`knowledge_date` support.** When the API supplies that column it outranks
  the declared knowledge field, and `kd_imputed=true` raises
  `ImputedKnowledgeDateWarning` — an imputed date is derived from a statutory
  filing deadline, not observed from an announcement, and is never presented as
  observed. Tracks `WORKORDER_API_expose_knowledge_date`.
- **Gaps with a stated source.** `Meta.gaps_source` is `server` (22 routes),
  `client_derived` (opt-in, computed against `trading_calendar`), `unsupported`,
  or `unknown`. Nothing is zero-filled, forward-filled or interpolated.
- **Truncation is visible.** Only 9 of 82 routes take `offset`;
  `Meta.truncated` says when a result was cut off.
- **`twmd.compat.finmind`** — FinMind-shaped calls served by TWMD, every mapping
  graded A/B/C/D. D-grade and unverified mappings raise `NotMappedError` instead
  of returning an empty frame, since an empty frame reads as "your query matched
  nothing" rather than "this does not exist here".
- **`TwmdFrame`**, a `pandas.DataFrame` subclass carrying `Meta` on `.twmd`.
  Without pandas the SDK returns `list[dict]` and still works.
- Free-tier mode with no API key for five demo symbols and the 16 datasets
  *measured* to serve them.
- `py.typed`, full annotations, generated `.pyi` for the 82 methods.

### Changed from 0.1.0

- `base_url` now defaults to `https://api.twmarketdata.com/v2`. 0.1.0 pointed at
  `https://twmarketdata.com`, which has been retired and returns
  **HTTP 410 `endpoint_retired`** — every 0.1.0 call fails today.
- Error classification follows the FRICTION-01 R2 contract (flat
  `{"error", "message"}` envelope; 402 entitlement, 403 authenticated-but-
  forbidden, 429 quota), plus `410 endpoint_retired`, plus
  **`403 temporarily_blocked` classified as a rate limit** rather than a
  permissions failure.
- `requests` replaces `httpx`. The 0.1.0 `transport=` parameter took an
  `httpx.BaseTransport`; pass `session=` a `requests.Session` instead.
- Default `max_concurrency` is 2. Four concurrent requests tripped a block that
  persisted for tens of minutes during measurement.
- The access tables (`OPEN_DATASETS` and friends) were re-measured. 0.1.0
  recorded 2 key-free datasets from a probe on 2026-07-21; a full 82-route sweep
  plus a non-demo-ticker sweep found 15 open and the same 3 sample-only. Names,
  semantics and return types unchanged.
- `iter_pages` / `get_all` stop when the server ignores `offset`. Measured on
  `index-constituents`, where offsets 0, 3 and 6 returned identical pages;
  continuing would append duplicates and present them as a full history.

### Deprecated

Still working, warning on use: `Client.get_dataset` / `get_all` / `iter_pages` /
`list_datasets` / `is_key_free`, the `twmd.access` and `twmd.frames` modules,
`to_dataframe`, `TWMarketDataClient`, and the `Twmd*Error` names
(`TwmdAPIError`, `TwmdPaymentRequired` with its `payment` / `price` /
`credits_url` / `purchase_hint` accessors, `TwmdRateLimitError`,
`TwmdTransportError`, `TwmdNotFoundError`, `TwmdValidationError`).

### Found while recording paid-tier responses

- **`limit` is capped per route, at five different values** (100 / 500 / 1000 /
  2000 / 5000); 56 of 82 are not 5000. Worse, the declared cap is not always the
  enforced one — `margin_system_stats` declares 5000 and rejects anything over
  1000. The SDK clamps from the registry, and if a 422 still names a lower cap
  it retries once at that value and says so.
- **`knowledge_date` is live on the four fundamentals** (`income_statement`,
  `balance_sheet`, `cash_flow_statement`, `financial_ratios`) — and every row
  carries `kd_imputed=true` with `kd_source=statutory_deadline`. Not one
  observed announcement timestamp. `as_of` on these datasets now warns even in
  server mode, so nobody running a server-side PIT backtest is the only party
  not told. Phase 1 then reached `monthly_revenue` as well.
- **`client_unsafe` datasets are probed, not refused outright.** The registry is
  a snapshot and the API is not: `knowledge_date` is rolling out dataset by
  dataset. Refusing before making the request left the refusal message's own
  promise ("if the API now returns a knowledge_date, this restriction lifts")
  permanently false. These datasets now cost one request before refusing, and
  when the response carries a real knowledge_date the query is answered with the
  imputed-date warning. Verified live on `monthly_revenue`: `as_of=2026-06-30`
  drops the June figure, whose knowledge date is 2026-07-10. Datasets with no
  declared knowledge axis at all still refuse without a request.
- **`report_date` is null on every income-statement row**, confirming the
  upstream writer gap on live paid data — which is why the knowledge date has to
  be imputed in the first place.
- **Rows sit at `envelope.data` on 9 datasets**, not just `price_enhanced`.
  Before the nested lookup they all returned empty frames.
- **`price_enhanced` really does serve adjustment factors, not OHLCV** —
  `event_type`, `factor`, `pre_event_close`, `reference_price`. `close` never
  appears, though the dataset contract declares it required.
- **A `max` plan does not include `developer`-tier datasets** (10 of them return
  402). The tiers are not one ladder.
- `400` / `422` now raise `ValidationError` instead of a generic error, keeping
  the server's wording — it is the only thing that names the offending field.

### Compat mappings settled against live rows

Seven candidates were checked column by column. Three were promoted, and two
were **withdrawn** — evidence that a substitution would mislead is as decisive
as evidence that it works:

- `taiwan_stock_market_value` → `valuation_core_daily` — **promoted**;
  `market_cap` is there, alongside `shares_outstanding` and the ratios.
- `taiwan_stock_convertible_bond_put_provision` → `convertible_bond_overview` —
  **promoted**; `put_start_date` / `put_end_date` / `put_price` all present.
- `taiwan_stock_news` → `company_news` — **kept, now precisely described**:
  headline, timestamp and link only. `metadata_only=true` and `summary=null`, so
  there is no article body to analyse, and the source is MOPS announcements
  rather than a press feed.
- `taiwan_stock_day_trading` → **withdrawn to D**. `price_move_context` carries
  `day_trade_ratio` but only has rows on large-move days, so serving it would
  return a silently biased sample rather than day-trading statistics.
- `taiwan_stock_convertible_bond_daily` → **withdrawn to D**.
  `convertible_bond_overview` has no OHLC at all, only `reference_price` —
  a different quantity from a traded price.

### Known limitations

- **Compat column names are TWMD's.** Parameter names are mirrored; response
  column names are not. Mirroring them would require comparing live responses
  from another service, which this project does not do. A `stock_id` alias is
  added where an identifier column exists.
- **Two compat mappings remain withheld** as unverified, down from nine. Both
  are blocked on access rather than on judgement: `etf_holdings` is
  developer-tier and returned 402 to a max key *and* to a developer key, and
  `taiwan_stock_10year` has no candidate dataset at all. They raise
  `NotMappedError` naming what is missing.
- **B-grade mappings without an implemented reshape refuse** and point at the
  native method, rather than returning the wrong shape.
- Paid-tier behaviour is covered by 63 recorded cassettes (2026-08-12, restricted
  key since deleted, auth headers redacted and asserted so by a test). Seven
  compat mappings remain unverified because their datasets are `developer`-tier
  and a `max` key does not reach them.
- Three datasets declared `tier=free` return 401 in practice
  (`valuation_data`, `issuer_profiles`, `industry_index`), so `tier` alone does
  not tell you what runs without a key. Use `twmd.runnable_without_key()`.

## 0.1.0 — 2026-07-21

Initial release (MIT). Retrieval-only client with `get_dataset`, pagination
helpers, an access-tier module and DataFrame conversion.
