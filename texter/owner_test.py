"""Send one forecast to the single verified owner number.

Refuses unless GARLAND_ALLOW_LIVE_SEND=1. Never reads a subscriber list.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from texter.sms_forecast import (
    CONFIG_PATH,
    active_alerts,
    apply_news,
    local_today,
    nws_days,
    render,
    seven_days,
)
from texter.twilio import TwilioAdapter, live_send_enabled, urllib_post


def forecast_body() -> str:
    config_path = CONFIG_PATH if CONFIG_PATH.exists() else Path(__file__).resolve().parents[1] / "examples" / "config.example.json"
    config = json.loads(config_path.read_text())
    now = local_today()
    days = seven_days([], nws_days(config, now), now)
    apply_news(days, "")
    return render(days, "", active_alerts(config))


def owner_destination(environ: dict[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    raw = env.get("TWILIO_TO", "").strip()
    if not raw.startswith("+") or not raw[1:].isdigit():
        raise SystemExit("TWILIO_TO must be one E.164 number")
    return raw


def run_owner_test(environ: dict[str, str] | None = None, http_post=None) -> dict:
    env = environ if environ is not None else os.environ
    if not live_send_enabled(env):
        return {"sent": False, "reason": "live send disabled"}
    destination = owner_destination(env)
    sender = env.get("TWILIO_FROM", "").strip()
    account_sid = env.get("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = env.get("TWILIO_AUTH_TOKEN", "").strip()
    if not sender.startswith("+") or not account_sid or not auth_token:
        return {"sent": False, "reason": "twilio secrets missing"}
    if destination == sender:
        return {"sent": False, "reason": "refusing to use the sender number as the only check"}
    body = env.get("GARLAND_TEST_BODY") or forecast_body()
    post = http_post or urllib_post(account_sid, auth_token)
    adapter = TwilioAdapter(
        from_number=sender,
        account_sid=account_sid,
        auth_token=auth_token,
        live_send=True,
        http_post=post,
    )
    result = adapter.send_sms(destination, body, "owner_test")
    return {
        "sent": result.accepted,
        "reason": result.error,
        "sid": result.provider_message_id,
        "status": result.detail,
    }


def main() -> int:
    outcome = run_owner_test()
    if not outcome["sent"]:
        print(outcome["reason"])
        return 2
    print("accepted")
    if outcome["sid"]:
        print(f"sid {outcome['sid']}")
    if outcome["status"]:
        print(f"status {outcome['status']}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
