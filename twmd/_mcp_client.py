"""往 MCP 伺服器打一次工具呼叫 —— 給 `twmd ask` 用。

## 為什麼 `ask` 要走 MCP 而不是 REST

實測(2026-08-25):

    GET https://api.twmarketdata.com/v2/ask      -> 404   `ask` 不在 REST 上
    GET https://api.twmarketdata.com/v2/search   -> 200,但 kind="docs",
                                                    查「月營收」回 0 筆 —— 那是文件搜尋,
                                                    不是資料集解析器

`ask` 是 **MCP 端的工具**。工單要求「路由到既有 ask,不新編邏輯」,那就只有一條
誠實的路:**呼叫那個工具**。在 CLI 裡自己寫一套「問句 → 資料集」的推斷,
就是新編邏輯,而且它會和 MCP 那邊的路由分岔 —— 同一個問題兩個答案。

## ⚠️ 這條路需要金鑰,而且不是每個方案都能用

`tools/call` 不在免金鑰白名單裡(免金鑰的只有握手、清單與參考資源)。
而且 `plan_allows_mcp` 實測 **free / starter 皆為 False** —— MCP 查詢從 Pro 起。

所以 `twmd ask` 對免費使用者會被擋,而**擋的訊息必須說清楚是方案問題**,
不是叫他去檢查金鑰。那條訊息走 `_cli_help.access_message`,和其他撞牆點同一套。

## 只做傳輸,不做解讀

這個模組把 JSON-RPC 打出去、把結果拆回來。**它不解釋答案** ——
答案品質等於既有 `ask` 路由的品質,工單也是這樣寫的。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_MCP_URL = "https://mcp.twmarketdata.com/mcp"
MCP_URL_ENV = "TWMD_MCP_URL"

#: SSE 前綴。伺服器以 text/event-stream 回應,即使只有一筆。
_DATA_PREFIX = "data: "


class McpUnavailable(RuntimeError):
    """連不上或伺服器沒有回一個可用的結果。"""


class McpAccessDenied(RuntimeError):
    """被擋下來了。`kind` 分辨「沒金鑰」和「方案不夠」—— 兩種處置不同。"""

    def __init__(self, message: str, *, kind: str = "auth") -> None:
        super().__init__(message)
        self.kind = kind


def mcp_url() -> str:
    return str(os.getenv(MCP_URL_ENV, "") or DEFAULT_MCP_URL).strip()


def call_tool(name: str, arguments: dict[str, Any], *, api_key: Optional[str] = None,
              timeout: float = 90.0, url: Optional[str] = None) -> dict[str, Any]:
    """呼叫一個 MCP 工具,回它的結構化結果。

    ⚠️ 401/403 分開丟:401 是「沒有可用的憑證」(設定問題),403 是「這個方案
    不能用 MCP」(方案問題)。把兩者合成一句 access denied,會讓一個只要設環境
    變數的人去買方案,或讓一個已經付費的人反覆檢查金鑰。
    """
    endpoint = url or mcp_url()
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}}).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(endpoint, data=body, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise McpAccessDenied("MCP rejected the credentials", kind="auth") from None
        if exc.code in (402, 403):
            raise McpAccessDenied("this plan does not include MCP access",
                                  kind="entitlement") from None
        raise McpUnavailable(f"MCP returned HTTP {exc.code}") from None
    except Exception as exc:  # noqa: BLE001
        raise McpUnavailable(f"could not reach {endpoint}: {type(exc).__name__}") from None

    payload = _decode(raw)
    if "error" in payload:
        message = str((payload.get("error") or {}).get("message") or "unknown MCP error")
        raise McpUnavailable(message)
    result = payload.get("result") or {}
    return _unwrap(result)


def _decode(raw: str) -> dict[str, Any]:
    for line in raw.splitlines():
        if line.startswith(_DATA_PREFIX):
            raw = line[len(_DATA_PREFIX):]
            break
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise McpUnavailable("MCP returned a body that is not JSON") from None


def _unwrap(result: dict[str, Any]) -> dict[str, Any]:
    """MCP 的 result 可能帶 structuredContent 或一串 content。

    ⚠️ 先看 `structuredContent`:那是工具真正的回傳值。只讀 `content` 的文字
    會拿到一段給人看的字串,而 CLI 要的是可以排成表格的結構。
    """
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            text = str(item.get("text") or "")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
            if isinstance(parsed, dict):
                return parsed
            return {"result": parsed}
    return result


def blocked_kind(error: BaseException) -> Optional[str]:
    return getattr(error, "kind", None) if isinstance(error, McpAccessDenied) else None
