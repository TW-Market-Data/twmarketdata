# 發版 0.6.2 —— 指令給 owner

> ⚠️ **token 是你的,我不碰、不發。** 下面每一條我都在本機跑過(除了最後的
> `twine upload`),所以它們不是憑印象寫的。

## 版號為什麼是 0.6.2 而不是 0.7.0

main 相對 **PyPI 0.6.1** 的差異,是**逐檔比對已發布的 sdist** 得到的,不是猜的:

```
新增模組   twmd/agent_schema.py
內容改動   twmd/_cli.py(+16 行:一個 `schema` 子指令)
其餘       完全相同
```

一個**純新增**的子指令,沒有任何既有行為改變、沒有移除、沒有改簽章 ——
那是 patch,不是 minor。0.7.0 要留給真的值得的那次。

## 發版前

```bash
cd /Volumes/DEV_USB/Projects/_wt/twmd-sdk

python3 -m pytest -q                 # 411 passed / 17 skipped
rm -rf dist build
python3 -m build                     # -> dist/twmarketdata-0.6.2{.tar.gz,-py3-none-any.whl}
python3 -m twine check dist/*        # 兩個都要 PASSED
```

⚠️ **裝起來實測一次**,不要只信 `twine check`:

```bash
python3 -m venv /tmp/relcheck
/tmp/relcheck/bin/pip install dist/twmarketdata-0.6.2-py3-none-any.whl
/tmp/relcheck/bin/twmd --version     # 必須是 0.6.2
/tmp/relcheck/bin/twmd schema | head # 新指令要真的在
```

理由:`tests/test_version_single_source.py` 在原始碼樹上會 **skip**(本機
egg-info 停在舊版),所以「裝起來會回什麼版本」在測試裡是**沒有被驗到的**。
我已經跑過這一段,實測回 `0.6.2`、`schema` 可用、`access=read_only`。

## 上傳(你來)

```bash
# 先上 TestPyPI 比較安全 —— 版本號一旦佔用就不能重發
python3 -m twine upload --repository testpypi dist/*

# 確認沒問題再上正式站
python3 -m twine upload dist/*
```

⚠️ **PyPI 的版本號不可重用。** 上傳後才發現漏東西,只能發 0.6.3 ——
所以上面那段「裝起來實測」建議真的跑,不要跳。

## 順帶修掉的一件事

⚠️ **0.6.0 和 0.6.1 兩個已發版本原本完全沒有 changelog,也沒有打 tag。**
已補上,而且兩則都標明是 **2026-08-28 從 PyPI 上已發布的 sdist 逐檔比對重建**的,
不是憑記憶寫的 —— 每一則開頭就列出重建依據。

建議這次順手把 tag 補回來(現有 tag 只到 `v0.5.0`):

```bash
git tag v0.6.0 <0.6.0 那次的 commit>   # 若查得到
git tag v0.6.1 <0.6.1 那次的 commit>
git tag v0.6.2
git push --tags
```

沒有 tag 的後果不是不好看:**下一次要問「0.6.1 到底發了什麼」時,唯一的辦法
就是我這次做的事 —— 下載 sdist 逐檔比對**。

## 費用

💰 沒有新的付費依賴。PyPI 發版免費。
