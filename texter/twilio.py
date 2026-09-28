"""Twilio request builder. Live HTTP is off unless GARLAND_ALLOW_LIVE_SEND=1."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode

from texter.messaging import Inbound, Outbound, SendResult


HttpPost = Callable[[str, dict[str, str], dict[str, str]], tuple[int, str]]


def live_send_enabled(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return env.get("GARLAND_ALLOW_LIVE_SEND") == "1"


def compute_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    payload = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def signature_is_valid(auth_token: str, url: str, params: dict[str, str], signature: str) -> bool:
    if not auth_token or not signature:
        return False
    expected = compute_signature(auth_token, url, params)
    return hmac.compare_digest(expected, signature)


@dataclass
class TwilioAdapter:
    from_number: str
    account_sid: str = ""
    auth_token: str = ""
    live_send: bool = False
    http_post: HttpPost | None = None

    def send_sms(self, to: str, body: str, kind: str = "forecast") -> SendResult:
        if not to.startswith("+") or not body or not self.from_number.startswith("+"):
            return SendResult(False, error="refusing incomplete payload")
        if not self.live_send:
            return SendResult(False, error="live send disabled")
        if not self.account_sid or not self.auth_token or self.http_post is None:
            return SendResult(False, error="live credentials or transport missing")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        status, response = self.http_post(
            url,
            {"To": to, "From": self.from_number, "Body": body},
            {"Authorization": "Basic redacted", "X-Kind": kind},
        )
        if status >= 400:
            return SendResult(False, error=f"provider status {status}", detail=response[:180])
        sid, message_status = _sid_and_status(response)
        return SendResult(True, provider_message_id=sid, detail=message_status)

    @staticmethod
    def parse_webhook(params: dict[str, str]) -> Inbound:
        return Inbound(
            sender=params.get("From", ""),
            body=params.get("Body", ""),
            provider_message_id=params.get("MessageSid", ""),
        )

    def accept_webhook(self, url: str, params: dict[str, str], signature: str) -> Inbound | None:
        if not signature_is_valid(self.auth_token, url, params, signature):
            return None
        return self.parse_webhook(params)


def _sid_and_status(response: str) -> tuple[str, str]:
    import json

    try:
        payload = json.loads(response)
    except json.JSONDecodeError:
        return "", ""
    return str(payload.get("sid") or ""), str(payload.get("status") or "")


def form_body(params: dict[str, str]) -> str:
    return urlencode(params)


def urllib_post(account_sid: str, auth_token: str) -> HttpPost:
    import urllib.error
    import urllib.request

    def post(url: str, params: dict[str, str], headers: dict[str, str]) -> tuple[int, str]:
        token = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        request = urllib.request.Request(
            url,
            data=urlencode(params).encode(),
            method="POST",
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    return post
