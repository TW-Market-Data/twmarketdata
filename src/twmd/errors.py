"""Exception hierarchy for the TWMD data-access client.

Every exception carries the raw decoded response body verbatim on ``.body`` so
callers can render whatever the API returned without this layer editing,
summarising, or dropping fields.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


class TwmdError(Exception):
    """Base class for every error raised by this client."""


class TwmdConfigError(TwmdError):
    """Client was constructed with an unusable configuration."""


class TwmdTransportError(TwmdError):
    """Network-level failure: DNS, connection, timeout, TLS."""


class TwmdAPIError(TwmdError):
    """The API returned a non-2xx response.

    Attributes:
        status_code: HTTP status code.
        body: Decoded response body, verbatim. ``None`` if the body was not
            valid JSON, in which case ``text`` holds the raw payload.
        text: Raw response text.
        error_code: The API's ``error`` field, when present.
        request_url: URL that produced this response.
    """

    def __init__(
        self,
        status_code: int,
        *,
        body: Optional[Mapping[str, Any]] = None,
        text: str = "",
        request_url: str = "",
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.text = text
        self.request_url = request_url
        self.error_code = body.get("error") if isinstance(body, Mapping) else None
        message = ""
        if isinstance(body, Mapping):
            message = str(body.get("message") or body.get("detail") or "")
        if not message:
            message = text[:200]
        super().__init__(f"HTTP {status_code}: {message}" if message else f"HTTP {status_code}")


class TwmdAuthError(TwmdAPIError):
    """HTTP 401. No API key was sent, or the key was rejected.

    Observed ``error`` codes:

    - ``missing_api_key`` — the request carried no key and the requested
      dataset/ticker combination is not in the key-free set. See
      :mod:`twmd.access`.
    - ``invalid_api_key`` — a key was sent but is unknown or revoked.

    As of the contract probe on 2026-07-21 this is the status returned for
    *unauthenticated* access to key-gated datasets. It is not a billing signal.
    """


class TwmdPaymentRequired(TwmdAPIError):
    """HTTP 402. A valid key whose plan does not include the requested dataset.

    This is distinct from 401: 401 means *no key* (or a bad key); 402 means the
    key is fine but the plan is insufficient. The two are not interchangeable —
    a 401 is answered by registering/adding a key, a 402 by upgrading a plan.

    Live contract (verified 2026-07-21)::

        402 {
          "error": "not_entitled_for_dataset",
          "message": "您的方案未包含此資料集…",
          "payment": {
            "price": <tier>,
            "credits_url": "https://twmarketdata.com/pricing",
            "purchase_hint": "upgrade_plan"
          }
        }

    The entire decoded body is preserved verbatim on ``.body`` — nothing is
    dropped. For convenience, the ``payment`` object and its fields are also
    exposed directly:

    Attributes:
        payment: The decoded ``payment`` object, or ``None`` if absent.
        price: ``payment.price`` (the tier), or ``None``.
        credits_url: ``payment.credits_url`` (where to upgrade), or ``None``.
        purchase_hint: ``payment.purchase_hint`` (e.g. ``"upgrade_plan"``), or ``None``.

    These accessors are read from whatever the API sent; they never fabricate a
    value. Upper layers should still prefer ``.body`` when they want to render
    the response faithfully, and treat the accessors as shortcuts.

    Example:
        >>> try:
        ...     client.get_dataset("institutional-flow", symbol="2330")
        ... except TwmdPaymentRequired as exc:
        ...     show_upgrade(exc.credits_url, exc.price)  # or exc.body, full & unmodified
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        payment = self.body.get("payment") if isinstance(self.body, Mapping) else None
        self.payment: Optional[Mapping[str, Any]] = payment if isinstance(payment, Mapping) else None
        p = self.payment or {}
        self.price = p.get("price")
        self.credits_url = p.get("credits_url")
        self.purchase_hint = p.get("purchase_hint")


class TwmdNotFoundError(TwmdAPIError):
    """HTTP 404. Unknown dataset path or resource."""


class TwmdValidationError(TwmdAPIError):
    """HTTP 422. The API rejected a parameter value.

    Note that the API tolerates *unknown* query parameters silently — it
    returns 200 and ignores them rather than raising 422. See
    :meth:`twmd.client.Client.get_dataset` for what that means for ``as_of``.
    """


class TwmdRateLimitError(TwmdAPIError):
    """HTTP 429. Retried automatically, honouring ``Retry-After`` when sent."""


class TwmdServerError(TwmdAPIError):
    """HTTP 5xx. Retried automatically."""


_STATUS_MAP = {
    401: TwmdAuthError,
    402: TwmdPaymentRequired,
    404: TwmdNotFoundError,
    422: TwmdValidationError,
    429: TwmdRateLimitError,
}


def error_for_status(
    status_code: int,
    *,
    body: Optional[Mapping[str, Any]] = None,
    text: str = "",
    request_url: str = "",
) -> TwmdAPIError:
    """Map an HTTP status code onto the matching exception class."""
    cls = _STATUS_MAP.get(status_code)
    if cls is None:
        cls = TwmdServerError if status_code >= 500 else TwmdAPIError
    return cls(status_code, body=body, text=text, request_url=request_url)
