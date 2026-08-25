"""`twmd` CLI —— 釘住三件不能省的行為,外加 exit code 的分類。

⚠️ 這支**不**驗「指令跑得起來」而已。跑得起來的 CLI 如果安靜地吞掉缺口、
或是對所有錯誤都回 1,會比沒有 CLI 更糟 —— 使用者會相信它。
"""

from __future__ import annotations

import json

import pytest

from twmd import _cli


def _run(capsys, argv):
    code = _cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --------------------------------------------------------------------------- 基本面

def test_help_exits_clean(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _cli.main(["--help"])
    assert excinfo.value.code == 0
    assert "Exit codes:" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["datasets", "describe", "coverage", "get", "auth", "version"])
def test_every_subcommand_has_its_own_help(capsys, command):
    """一個沒有 --help 的子指令,等於要求使用者去讀原始碼。"""
    with pytest.raises(SystemExit) as excinfo:
        _cli.main([command, "--help"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip()


def test_version_prints_the_sdk_version(capsys):
    import twmd

    code, out, _ = _run(capsys, ["version"])
    assert code == _cli.EXIT_OK
    assert out.strip() == twmd.__version__


def test_datasets_lists_real_registry_entries(capsys):
    import twmd

    code, out, err = _run(capsys, ["datasets", "--format", "json"])
    assert code == _cli.EXIT_OK
    rows = json.loads(out)
    assert {r["dataset"] for r in rows} == set(twmd.datasets())
    assert "runs without an API key" in err


def test_free_only_matches_the_registry_not_a_hand_written_list(capsys):
    """⚠️ 「哪些免金鑰」只有一個真相源。CLI 自己記一份,遲早和 registry 分家。"""
    import twmd

    _, out, _ = _run(capsys, ["datasets", "--free-only", "--format", "json"])
    assert {r["dataset"] for r in json.loads(out)} == set(twmd.runnable_without_key())


def test_describe_surfaces_the_as_of_semantics(capsys):
    """取數**之前**就要知道這個資料集的 as_of 語意,而不是拿到 200 之後。"""
    code, out, _ = _run(capsys, ["describe", "monthly_revenue"])
    assert code == _cli.EXIT_OK
    assert "how to read as_of" in out


def test_coverage_separates_no_rows_from_no_coverage(capsys):
    code, out, err = _run(capsys, ["coverage", "monthly_revenue"])
    assert code == _cli.EXIT_OK
    assert "coverage_start" in out
    assert "we do not cover that period" in err


# --------------------------------------------------------------------------- 三件不能省的事

def test_omitting_as_of_warns_on_stderr(capsys, monkeypatch):
    """**#1。** 終端機使用者不會讀 docstring,而這是未來函數進到回測的那條路。"""
    monkeypatch.setattr(_cli, "_rows_of", lambda _r: [])

    class _Client:
        def __init__(self, *_a, **_k): pass
        def dataset(self, *_a, **_k): return []
        def close(self): pass

    import twmd
    monkeypatch.setattr(twmd, "Client", _Client)
    code, _, err = _run(capsys, ["get", "monthly_revenue"])
    assert code == _cli.EXIT_OK
    assert "look-ahead leak" in err
    assert "--as-of" in err


def test_passing_as_of_does_not_warn(capsys, monkeypatch):
    """負向對照:給了 as_of 還警告,使用者會學會忽略所有警告。"""
    class _Client:
        def __init__(self, *_a, **_k): pass
        def dataset(self, *_a, **_k): return []
        def close(self): pass

    import twmd
    monkeypatch.setattr(twmd, "Client", _Client)
    _, _, err = _run(capsys, ["get", "monthly_revenue", "--as-of", "2024-06-30"])
    assert "look-ahead leak" not in err


def test_sdk_warnings_reach_stderr_not_the_data(capsys, monkeypatch):
    """**#2。** SDK 用 warnings 表達缺口/截斷,而 Python 預設同一個只印一次,
    且它們不在 stdout 的資料裡。CLI 不接住,`--format csv > out.csv` 的人永遠看不到。"""
    import warnings as _w

    import twmd

    class _Client:
        def __init__(self, *_a, **_k): pass

        def dataset(self, *_a, **_k):
            _w.warn("rows are missing for 3 periods", twmd.PITDataMissingWarning, stacklevel=1)
            return [{"ticker": "2330", "value": 1}]

        def close(self): pass

    monkeypatch.setattr(twmd, "Client", _Client)
    code, out, err = _run(capsys, ["get", "monthly_revenue", "--as-of", "2024-06-30",
                                   "--format", "csv"])
    assert code == _cli.EXIT_OK
    assert "rows are missing for 3 periods" in err
    # ⚠️ 資料那一邊必須是乾淨的 CSV —— 警告混進 stdout 會讓下游 parser 壞掉,
    # 而那會讓人把警告關掉。
    assert "rows are missing" not in out
    assert out.splitlines()[0] == "ticker,value"


def test_a_repeated_warning_is_not_swallowed(capsys, monkeypatch):
    """負向對照:Python 預設會把重複的警告吃掉 —— 每一列缺口都值得被看到。"""
    import warnings as _w

    import twmd

    class _Client:
        def __init__(self, *_a, **_k): pass

        def dataset(self, *_a, **_k):
            for _ in range(3):
                _w.warn("gap", twmd.PITDataMissingWarning, stacklevel=1)
            return []

        def close(self): pass

    monkeypatch.setattr(twmd, "Client", _Client)
    _, _, err = _run(capsys, ["get", "monthly_revenue", "--as-of", "2024-01-01"])
    assert err.count("note: gap") == 3


# --------------------------------------------------------------------------- #3 exit code

@pytest.mark.parametrize("exc_name,expected", [
    ("MissingApiKeyError", _cli.EXIT_AUTH),
    ("InvalidApiKeyError", _cli.EXIT_AUTH),
    ("TierRequiredError", _cli.EXIT_ENTITLEMENT),
    ("InsufficientCreditsError", _cli.EXIT_ENTITLEMENT),
    ("DatasetNotFoundError", _cli.EXIT_NOT_FOUND),
    ("RateLimitedError", _cli.EXIT_RATE_LIMITED),
    ("ValidationError", _cli.EXIT_VALIDATION),
    ("TwmdServerError", _cli.EXIT_UPSTREAM),
])
def test_each_failure_class_gets_its_own_exit_code(exc_name, expected):
    """**#3。** 額度不足 / 權限不足 / 找不到資料集是三種不同的 shell 處置。

    ⚠️ 全部回 1 等於逼使用者去 grep 錯誤訊息字串 —— 而訊息是會改的。
    """
    from twmd import errors

    exc_type = getattr(errors, exc_name)
    try:
        raise exc_type("x")
    except Exception as exc:  # noqa: BLE001
        assert _cli._exit_code_for(exc) == expected


def test_the_exit_codes_are_distinct():
    """負向對照:兩個成因共用一個 code,就等於沒有分類。"""
    codes = [_cli.EXIT_AUTH, _cli.EXIT_ENTITLEMENT, _cli.EXIT_NOT_FOUND,
             _cli.EXIT_RATE_LIMITED, _cli.EXIT_VALIDATION, _cli.EXIT_UPSTREAM]
    assert len(set(codes)) == len(codes)
    assert _cli.EXIT_USAGE == 2, "argparse 自己會用 2,別佔用它"


def test_an_unknown_dataset_exits_not_found(capsys):
    """走真的 registry —— 這條同時證明錯誤分類接到了既有的例外階層。"""
    code, _, err = _run(capsys, ["describe", "definitely_not_a_dataset"])
    assert code == _cli.EXIT_NOT_FOUND
    assert "Unknown dataset" in err


def test_an_auth_failure_tells_the_user_what_still_works(capsys, monkeypatch):
    """一個只說「沒有金鑰」的錯誤,會讓人以為什麼都不能做。"""
    import twmd
    from twmd import errors

    class _Client:
        def __init__(self, *_a, **_k): raise errors.MissingApiKeyError("no key")

    monkeypatch.setattr(twmd, "Client", _Client)
    monkeypatch.delenv("TWMD_API_KEY", raising=False)
    code, _, err = _run(capsys, ["get", "balance_sheet", "--as-of", "2024-01-01"])
    assert code == _cli.EXIT_AUTH
    assert "--free-only" in err


# --------------------------------------------------------------------------- 安全

def test_auth_status_never_echoes_the_key(capsys, monkeypatch):
    """⚠️ `auth status` 是最容易被貼進工單 / issue 的輸出。"""
    monkeypatch.setenv("TWMD_API_KEY", "sk_live_averysecretvalue123456")
    code, out, _ = _run(capsys, ["auth"])
    assert code == _cli.EXIT_OK
    assert "averysecretvalue" not in out
    assert "sk_live_" in out and "chars" in out


def test_a_subclass_never_falls_into_its_parents_bucket():
    """⚠️ **這條是排序抓到的真 bug。**

    `TierRequiredError` / `InsufficientCreditsError` 都繼承自 `TwmdAuthError`,
    所以 auth 那條放前面會把它們一起吃掉 —— 「沒有金鑰」和「方案不夠」變成
    同一個 code,而那是兩種處置:一個去設環境變數,一個去升級方案。
    """
    from twmd import errors

    assert issubclass(errors.TierRequiredError, errors.TwmdAuthError), "前提變了,重看這個對映"
    assert _cli._exit_code_for(errors.TierRequiredError("x")) != \
        _cli._exit_code_for(errors.MissingApiKeyError("x"))
    assert issubclass(errors.DatasetNotFoundError, errors.TwmdRequestError)
    assert _cli._exit_code_for(errors.DatasetNotFoundError("x")) != \
        _cli._exit_code_for(errors.TwmdRequestError("x"))


def test_the_cli_reads_rows_without_pandas():
    """⚠️ 為了一個命令列把安裝體積變三倍,會讓人選擇不裝。

    沒有 pandas 時 `Client.dataset()` 回**純 list of dict**,CLI 要吃得下 ——
    釘的是那個行為,不是原始碼裡有沒有出現 'pandas' 這個字。
    """
    assert _cli._rows_of([{"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]
    assert _cli._rows_of([]) == []
    assert _cli._rows_of(None) == []


def test_pandas_is_not_a_hard_dependency_and_the_entry_point_is_declared():
    """裝了 `twmarketdata` 之後 `twmd` 就要能用,而且不該順帶拖進 pandas。"""
    import pathlib
    import re

    text = (pathlib.Path(_cli.__file__).resolve().parents[1]
            / "pyproject.toml").read_text(encoding="utf-8")
    deps = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.S | re.M).group(1)
    assert "pandas" not in deps, "pandas 進了主依賴"
    assert re.search(r"^\s*twmd\s*=\s*\"twmd\._cli:main\"", text, re.M), "沒有宣告 console_script"
