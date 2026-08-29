# 發布前阻斷清單

**狀態(2026-08-29 實測):阻斷 1、2 皆已解除。`0.6.2` 已在 PyPI 上。**

發布步驟見 `RELEASE_CHECKLIST.md`(owner 執行)。

> ⚠️ **這份文件在 2026-08-12 到 08-29 之間是錯的。** 它一直寫著「尚不可發布」,
> 而同一段期間 repo 發出了 **8 個版本**(0.2.0 → 0.6.2)。一份說「不能發」而
> 實際上一直在發的阻斷清單,比沒有清單更糟 —— 讀的人會以為還有東西擋著,
> 而真正該擋的東西(見下面「現行阻斷」)沒有人在看。
>
> 所以這一版的每一個數字都是**當天重跑出來的**,不是抄上一版的。

---

## 權威狀態:PyPI(2026-08-29 實測)

```
GET https://pypi.org/pypi/twmarketdata/json
  latest    0.6.2
  license   Apache-2.0
  releases  0.1.0, 0.2.0, 0.2.1, 0.3.0, 0.4.0, 0.5.0, 0.6.0, 0.6.1, 0.6.2
```

⚠️ **`CHANGELOG.md` 的 `## 0.6.2 — 未發布` 和 PyPI 對不起來。** PyPI 是權威。
兩者之一要改 —— 這是 owner 的決定(補上發布日期,或確認那是一個誤標)。

---

## 阻斷 1 —— ✅ 已解除(裁決 2026-08-12,B 案)

續發 `twmarketdata` 0.2.0,import 名維持 `twmd`,0.1.0 的公開面全部保留為
deprecated alias(`twmd/_legacy.py`,有從已發布 wheel introspect 出來的測試逐項把關)。
0.1.0 維持 MIT,0.2.0 起 Apache-2.0。

**已執行完畢**:PyPI 上 0.6.2 的授權欄位就是 `Apache-2.0`,`pyproject.toml` 的
publish banner 已於 `53966fc` 移除。

<details>
<summary>當時的分析與被否決的 A / C 案(保留供查證)</summary>

原始問題:`twmarketdata` 0.1.0(2026-07-21 上傳,MIT)已經在 PyPI 上,import 名
就是 `twmd`;而 `twmd` 這個 dist 名沒被佔(404)。原始碼在
`/Volumes/DEV_USB/Projects/twmd-python-client`。**是我們自己的套件**,不是別人佔名。

| | 作法 | 代價 |
|---|---|---|
| **A** | 發成 `twmd` | 兩個 dist 都提供 `twmd` 模組,同時安裝互相覆蓋 —— 否決 |
| **B** ✅ | 續發 `twmarketdata` 0.2.0 + deprecated alias | 補一層相容 shim,但沒人被弄壞 |
| **C** | 併回 `twmd-python-client` 當 0.2.0,維持 MIT | 少一次授權變更;但放棄 Apache 的專利授權條款 |

</details>

---

## 阻斷 2 —— ✅ 已解除(受限測試 key 已取得並用畢)

當時卡在「拿不到受限測試 key」的五項,**現況實測**:

| 項目 | 當時 | 現況 |
|---|---|---|
| 付費層 cassette 錄製 | 卡住 | ✅ `tests/cassettes/` 有 **63 個** cassette |
| 9 列 low 信心映射逐列驗證 | 卡住 | ✅ 於 `b4ea9ec` / `6b9258b` 完成(entitlement 修正後重錄) |
| `client_unsafe` → `client` 升級評估 | 卡住 | ✅ 同上批次 |
| pro / max 範例 | 卡住 | ✅ 已隨版本發布 |
| `ResponseMeta` 四個 `X-TWMD-*` header 是否只在帶 key 時出現 | 卡住 | ✅ 已錄進 cassette |

紀律(仍然有效,下次要 key 時照走):owner 在 enterprise console 自產受限 key →
錄 cassette → **用完刪 key**。cassette 進 repo 前 redact `X-API-Key` / `Authorization`,
`tools/audit_public_repo.py` 在 CI 第一關擋住未遮罩者。
⚠️ **enterprise key 不進 repo、不進 chat。**

---

## 現行阻斷

### 🔴 無 —— 目前沒有東西擋住發布

### 🟡 待 owner 裁的兩件

1. **`CHANGELOG.md` 的 `0.6.2 — 未發布` 與 PyPI 不一致**(見上)。

2. **`tools/check_registry_drift.py` 現在跑不了** —— 實測回
   `could not reach the API (HTTP Error 403: Forbidden); skipping drift check`。

   ⚠️ 這一條值得注意的不是它失敗,是它**失敗得太安靜**:它印一行訊息然後
   `skipping`,而不是非零退出。一個「registry 有沒有漂移」的檢查,在 API 擋住
   我們的時候回報「跳過」—— 在 CI 上和「檢查過了,沒漂移」長得幾乎一樣。

   403 最可能是免 key 的公開端點加了 Cloudflare 或 key 要求。要嘛給它一把免費
   key,要嘛讓它在跑不到時**非零退出**。這是 owner 的選擇,我不代決。

---

## 發布前檢查 —— 2026-08-29 實測

```
$ python tools/audit_public_repo.py
ok   secrets
ok   retired base URL
ok   package contents
Audit clean: no credentials, no retired base URL, package ships only the client.

$ pytest -q -m "not network"     401 passed,  27 deselected
$ pytest -q -m network            11 passed,  16 skipped
```

⚠️ 上一版寫的是 `96 passed` / `9 passed` —— 相差四倍以上。抄上一版的數字,會讓
一份「剛驗過」的報告描述十七天前的 repo。

⚠️ **那 16 個 skip 不是缺 key**,是 `TWMD_LIVE_ALL=1` 這個 opt-in 全掃開關沒開
(`tests/test_live_free_tier.py:124`)。要全掃就設那個環境變數 —— 這是一個
選擇,不是一個阻斷。

### ⚠️ 稽核在這次更新前是 **FAIL**,而 0.6.2 已經發出去了

```
FAIL secrets (1):
    tests/test_cli.py:226: possible live API key
Audit failed. Nothing should be published until this is clean.
```

實際上是**誤報**:那是 `test_auth_status_never_echoes_the_key` 的合成夾具
(`sk_live_averysecret…`),不是真金鑰。但它讓「不乾淨就不發布」這道閘長期紅著,
而版本照發 —— 也就是說**那道閘實際上沒有在擋任何東西**。

修法是換夾具,不是放寬規則:`tools/audit_public_repo.py` 對 `sk_test_notreal`
有明確豁免、對 `sk_live_` **刻意沒有**。夾具改用被認可的前綴後稽核轉綠,
而測試強度沒有變 —— 遮罩是 `key[:8]`(`twmd/_cli.py:442`),不分 live/test,
兩種前綴都剛好 8 個字元。

⚠️ 讓 `sk_live_` 保持成一條**無法豁免**的絆線,是這裡比較強的安全姿態。
