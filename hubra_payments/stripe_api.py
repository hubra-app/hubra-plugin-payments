"""The few Stripe API calls the plugin makes, with the standard library.

Every call uses the platform's secret key (manage › Payments). Calls for a
club's account carry its id in the ``Stripe-Account`` header, so the
checkout is the club's own (a direct charge): the money, the refunds and the
Stripe fees are the club's.
"""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.stripe.com"
VERSION = "2024-06-20"
TIMEOUT = 20


class StripeError(Exception):
    """Stripe refused a call, or could not be reached."""

    def __init__(self, message: str, status: int = 0, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


def _flatten(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: a[b][0][c]=x."""
    out: list[tuple[str, str]] = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            out += _flatten(value, name)
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    out += _flatten(item, f"{name}[{i}]")
                else:
                    out.append((f"{name}[{i}]", str(item)))
        elif isinstance(value, bool):
            out.append((name, "true" if value else "false"))
        else:
            out.append((name, str(value)))
    return out


def _send(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, bytes]:
    """One HTTP request; tests replace this."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def call(
    key: str,
    method: str,
    path: str,
    data: dict | None = None,
    account: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {key}",
        "Stripe-Version": VERSION,
        "User-Agent": "Hubra-Payments/1.0",
    }
    if account:
        headers["Stripe-Account"] = account
    url = API + path
    body = None
    encoded = urllib.parse.urlencode(_flatten(data or {}))
    if method == "GET":
        if encoded:
            url += "?" + encoded
    else:
        body = encoded.encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Idempotency-Key"] = idempotency_key or secrets.token_hex(16)
    try:
        status, raw = _send(method, url, headers, body)
    except OSError as exc:
        raise StripeError(f"Stripe is not reachable: {exc}") from exc
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {}
    if status >= 400:
        err = payload.get("error") or {}
        raise StripeError(
            err.get("message") or f"Stripe answered {status}", status, err.get("code")
        )
    return payload


# ── Accounts ─────────────────────────────────────────────────────────────────


def create_account(key: str, email: str | None, name: str | None) -> dict:
    """A Standard account in Switzerland; the club fills in the rest at Stripe."""
    return call(
        key,
        "POST",
        "/v1/accounts",
        {
            "type": "standard",
            "country": "CH",
            "email": email or None,
            "business_profile": {"name": name} if name else None,
        },
    )


def account_link(key: str, account: str, refresh_url: str, return_url: str) -> str:
    link = call(
        key,
        "POST",
        "/v1/account_links",
        {
            "account": account,
            "refresh_url": refresh_url,
            "return_url": return_url,
            "type": "account_onboarding",
        },
    )
    return link["url"]


def get_account(key: str, account: str) -> dict:
    return call(key, "GET", f"/v1/accounts/{urllib.parse.quote(account)}")


# ── Checkout ─────────────────────────────────────────────────────────────────


def create_checkout(key: str, account: str, data: dict, idempotency_key: str) -> dict:
    return call(
        key,
        "POST",
        "/v1/checkout/sessions",
        data,
        account=account,
        idempotency_key=idempotency_key,
    )


def get_checkout(key: str, account: str, session_id: str) -> dict:
    return call(
        key,
        "GET",
        f"/v1/checkout/sessions/{urllib.parse.quote(session_id)}",
        {"expand": ["payment_intent.payment_method"]},
        account=account,
    )


def expire_checkout(key: str, account: str, session_id: str) -> dict:
    return call(
        key,
        "POST",
        f"/v1/checkout/sessions/{urllib.parse.quote(session_id)}/expire",
        account=account,
    )
