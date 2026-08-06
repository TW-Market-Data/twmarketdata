[English](README.md) · [繁體中文](README.zh-TW.md) · **简体中文**

# twmd — Python 台股市场数据客户端

[![PyPI](https://img.shields.io/pypi/v/twmarketdata)](https://pypi.org/project/twmarketdata/)
[![Python](https://img.shields.io/pypi/pyversions/twmarketdata)](https://pypi.org/project/twmarketdata/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/twmarketdata)](https://pypi.org/project/twmarketdata/)

**[TW Market Data](https://twmarketdata.com)** API 的官方 Python 客户端 —— 上市（TWSE）／
上柜（TPEx）行情、财务报表、机构买卖、估值与因子数据,共 80+ 数据集,以 pandas
DataFrame 返回。**五只样本股免密钥即可查询**,一行就能试。

```bash
pip install twmarketdata
```
```python
from twmd import Client
Client().get_dataset("twse-daily-price", symbol="2330", limit=5)   # 免密钥
```

**开始使用:** [免费 API 密钥](https://twmarketdata.com) · [方案定价](https://twmarketdata.com/pricing) · [文档](https://twmarketdata.com/docs) · [数据集目录](https://twmarketdata.com/datasets) · [MCP / AI agents](https://twmarketdata.com/docs/tools-and-mcp)

---

`twmd` 通过 HTTP 取回已发布的数据集,并返回为 pandas DataFrame。它是一层数据取回的
传输层,供研究与教育用途。它按 API 发布的样子取回记录,不做任何分析、评分、排序或
解读。数据代表什么、以及要不要据此行动,完全是调用方自己的工作与责任。

响应会带着 API 本身的 `lineage.not_investment_advice` 标志,本客户端原样保留。

## 安装

```bash
pip install twmarketdata
```

发行包名为 `twmarketdata`;导入的包名是 `twmd`:

```python
import twmd
```

纯 Python。依赖只有 `httpx` 与 `pandas` —— 无编译扩展、无系统库,可安装于受限沙箱中。

需要 Python 3.9 以上。依赖下限刻意压低（`pandas>=1.5`、`httpx>=0.27`）,好让它能装进
现有环境而不强制升级;CI 会用这些下限精确锁定跑完整测试,让它们保持诚实而非空谈。

有一个不是我们能修的注意事项:pandas 1.5 的 wheel 是针对 numpy 1.x 的 C ABI 编译的,在
numpy 2 下导入会以 `numpy.dtype size changed` 失败。若你被锁在 pandas 1.x,请一并锁
`numpy<2`。pandas 2.2.2 以后则可在不限制 numpy 2 的情况下运行。

## 快速开始 —— 免密钥

在选定的数据集上,五只样本股免凭证即可取用,以下零配置就能跑:

```python
from twmd import Client

client = Client()
df = client.get_dataset("twse-daily-price", symbol="2330", limit=5)

print(df[["date", "open", "high", "low", "close", "volume_shares"]])
print(df.attrs["data_as_of"])       # 数据新鲜度日期
print(df.attrs["lineage"])          # 提供者、来源端点、来源数据表
```

## 为什么选 twmd

- **官方来源,明白标示。** 每条响应都带 `lineage` —— 提供者、官方来源端点、来源数据表
  —— 以及 `data_as_of` 新鲜度日期。不捏造、不插值、不回填。
- **只取数据,不夹带观点。** 本客户端只取回数据;不产生任何分数、信号或建议。数据
  代表什么,由你自己判断。
- **诚实的覆盖范围。** 数据集只报告它实际拥有的内容。缺漏就显示为缺漏 —— 绝不用零
  或别只股票的数据行填补。
- **纯 Python。** `httpx` + `pandas`,无编译扩展 —— 到处都能装,连受限沙箱也行。CI 在
  Linux／macOS／Windows 上跨 Python 3.9–3.13 验证。
- **也为 AI agent 而生。** 同一批数据可通过 [MCP](https://twmarketdata.com/docs/tools-and-mcp)
  与 [`llms.txt`](https://twmarketdata.com/llms.txt) 索引取用,让 agent 直接发现并查询
  数据集。

## 认证

在环境变量中设置你的密钥;它绝不写入磁盘、也不记入日志:

```bash
export TWMD_API_KEY="sk_live_..."
```

`Client()` 会自动读取。你也可以显式传入 `Client(api_key=...)`。未设密钥时,客户端以
免密钥模式运行,可取用下方列出的数据集。

## 免密钥取用对照表

免密钥取用是**逐数据集**界定的,不是全局逐只股票。同一只股票在某个数据集免密钥,在
另一个数据集可能就需要密钥。以下为 2026-07-21 对线上 API 实测:

| 层级 | 数据集 | 免密钥可查的股票 |
| --- | --- | --- |
| 开放 | `security-master`、`market-index` | 任意 |
| 样本 | `twse-daily-price`、`tpex-daily-price`、`monthly-revenue` | 仅 `2330`、`2317`、`2454`、`0050`、`2603` |
| 需密钥 | 其余全部,含 `institutional-flow`、`market-prices`、`financial-metrics`、`income-statement`、`balance-sheet` | 无 |

请求前先检查:

```python
from twmd import is_key_free

is_key_free("twse-daily-price", "2330")     # True
is_key_free("twse-daily-price", "1101")     # False —— 不在样本股之列
is_key_free("security-master", "1101")      # True —— 开放数据集
is_key_free("institutional-flow", "2330")   # False —— 需密钥
```

不在表中的数据集一律视为需密钥,这是安全的默认。客户端绝不会据此拦下请求 —— 它只
用这张表在事后解释 401。

## DataFrame 与元数据

记录变成数据行。响应信封中的其余一切都保留在 `df.attrs`。

API 使用**两种信封形状**,`twmd` 两者都会透明处理:

```python
# rows / count —— twse-daily-price、tpex-daily-price、monthly-revenue
df.attrs["dataset"]       # "twse_daily_price"
df.attrs["count"]         # 记录条数
df.attrs["data_as_of"]    # 数据新鲜度日期
df.attrs["source_role"]   # 例如 "official_twse"
df.attrs["lineage"]       # 提供者、官方来源、来源端点、数据表
df.attrs["meta"]          # 最后交易日、市场状态

# items / row_count —— security-master、market-index
df.attrs["dataset_id"]                  # "security-master"
df.attrs["row_count"]                   # 记录条数
df.attrs["as_of_date"]                  # 快照日期
df.attrs["survivorship_bias_warning"]   # API 提出的完整性注意事项
```

信封内容因数据集而异 —— `monthly-revenue` 只发送 `dataset`、`rows`、`count` —— 所以读
`attrs` 要防御性一点。

`items` 变体中的记录含嵌套对象（`security_identity`、`market_identity`、`index_level`）。
它们保持为 dict 值的字段而不展平,好让 DataFrame 反映 API 实际发送的内容。需要时
再展开:

```python
import pandas as pd
identity = pd.json_normalize(df["security_identity"])
```

注意 `security-master` 带有 `survivorship_bias_warning`,声明当前的主表并非时间点完整
（point-in-time complete）。它原样呈现在 `attrs` 上;用该数据集做历史分析前请先检查。

## 错误

```python
from twmd import Client, TwmdAuthError, TwmdPaymentRequired

try:
    df = client.get_dataset("institutional-flow", symbol="2330")
except TwmdAuthError as exc:
    print(exc.error_code)   # "missing_api_key" 或 "invalid_api_key"
    print(exc.body)         # 解码后的响应内容,原文照录
```

每个 `TwmdAPIError` 子类 —— 下表除最后一行外的每一行 —— 都提供 `.status_code`、
`.body`（解码后、未修改的内容）、`.text` 与 `.error_code`。`TwmdTransportError` 与
`TwmdConfigError` 直接派生自 `TwmdError`,因为没有收到响应,故不带上述属性。

| 状态码 | 异常 | 是否重试 |
| --- | --- | --- |
| 401 | `TwmdAuthError` | 否 |
| 402 | `TwmdPaymentRequired` | 否 |
| 404 | `TwmdNotFoundError` | 否 |
| 422 | `TwmdValidationError` | 否 |
| 429 | `TwmdRateLimitError` | 是 |
| 5xx | `TwmdServerError` | 是 |
| 网络失败 | `TwmdTransportError` | 是 |

重试采用带抖动的指数退避。`Retry-After` 标头 —— 无论是 RFC 7231 的 delta-seconds 或
HTTP-date 形式 —— 会覆盖前述机制并被精确遵守,不加抖动、不缩短,因为比服务器允许的
时间更早重试,比等太久更糟。若它要求超过 `RETRY_AFTER_MAX`（120 秒）,客户端会停止
并抛出服务器的错误,而非卡住数分钟。

401 消息会标注你所请求的数据集与股票的免密钥状态,让「我忘了带密钥」能与「那只
股票不在样本股之列」区分开来。

### 401 与 402 的区别

两者含义不同,解法也不同:

- **401** —— 没带密钥,或密钥无效。用注册／新增密钥来解决。
- **402** —— 密钥有效,但**方案未包含**该数据集。用升级方案来解决。

线上 402 响应内容（2026-07-21 验证）:

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

整段内容原文保留在 `.body`。为方便起见,`payment` 对象及其字段也暴露在异常上 —— 一律
读 API 实际发来的值,绝不捏造:

```python
except TwmdPaymentRequired as exc:
    exc.payment        # payment 对象,或 None
    exc.price          # "pro"
    exc.credits_url    # "https://twmarketdata.com/pricing"
    exc.purchase_hint  # "upgrade_plan"
    exc.body           # 完整响应,未修改
```

## 来源标记

传入 `source` 为每个请求标上产生它的集成来源,让发布者能归因流量:

```python
client = Client(source="ecosys/tradingagents")
```

它会作为 `source` 查询参数附在每个请求上。`get_dataset` 上逐次的 `source=` 会覆盖
客户端级别的值。它是一个普通查询参数 —— 不改变响应、不进入数据响应的
`request_context.filters`、也不带任何用户信息。不设就不发送。

## 分页

```python
df = client.get_all("twse-daily-price", symbol="2330", limit=1000)

for page in client.iter_pages("twse-daily-price", symbol="2330", limit=500):
    process(page)
```

API 不发布游标:任何响应或 OpenAPI 文档中都没有 `cursor` 或 `next_cursor` 字段。分页
是 `limit`/`offset`,而 `offset` 经实测在免密钥端点上被**忽略** —— `offset=3` 返回与
`offset=0` 相同的记录。

所以这里的分页是防御性的。它按文档推进 `offset`,然后在以下两种情况停止:某页返回
条数少于 `limit`,或某页重复了前一页的第一条记录 —— 那是 `offset` 被静默忽略的特征。
对忽略 `offset` 的端点,这会恰好产生一页,那是正确结果而非失败。`max_pages` 为循环
设上限。

## `as_of`

`get_dataset()` 接受 `as_of` 参数并将它作为查询参数转发。**它的适用范围很窄。** 按
2026-07-21 实测:

- `as_of` 仅声明于四个端点 —— `income-statement`、`cash-flow-statement`、
  `balance-sheet`、`financials` —— 且都需要 API 密钥。
- 在其余每个端点它都不是已声明的参数。API 会静默忽略未知的查询参数,返回 200 而非
  422,所以在那些端点传 `as_of` 没有可观察的效果、也不会报错。
- 它在那四个已声明端点上的行为,本项目**未验证**,因为没有凭证可实测。

请把 `as_of` 当成「已转发但未确认」,而非通用的时间点查询机制。响应中的 `data_as_of`
字段是数据新鲜度日期,是另一回事。

## 开发

```bash
pip install -e ".[test]"
pytest -m "not live"    # 离线,不联网
pytest -m live          # 打真正的 API,仅免密钥路径
```

live 测试会断言免密钥对照表的一个样本 —— 七组数据集／股票配对 —— 仍与 API 提供的
一致,所以这些表面的漂移会以测试失败浮现。它是一条绊线,不是完整覆盖:五只样本股仅
对 `twse-daily-price` 验证,而三个列为需密钥的数据集是假定而非实测（见
`access.PRESUMED_KEY_REQUIRED_DATASETS`,以及 `access.provenance()` 可分辨两者）。

## 适用范围

本包负责取回数据。它不产生任何关于任何证券的建议、预测、信号、估值或观点,其返回
的内容也不应被如此解读。数据供研究与教育用途;在据此行动前,请对照原始来源核查。
使用底层 API 受 TW Market Data 自身条款约束。

## 许可证

MIT
