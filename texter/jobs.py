"""Schedule entry points. Live sending stays off unless the environment enables it."""

from __future__ import annotations

import os
from pathlib import Path

from texter.service import WeatherService
from texter.store import JsonStore
from texter.twilio import TwilioAdapter, live_send_enabled

WELCOME = Path(__file__).resolve().parents[1].joinpath("templates", "welcome.txt")


def build_service(store_path: Path, environ: dict[str, str] | None = None, http_post=None) -> WeatherService:
    env = environ if environ is not None else os.environ
    welcome = WELCOME.read_text().strip() if WELCOME.exists() else "You're on the Garland weather texts."
    adapter = TwilioAdapter(
        from_number=env.get("TWILIO_FROM", ""),
        account_sid=env.get("TWILIO_ACCOUNT_SID", ""),
        auth_token=env.get("TWILIO_AUTH_TOKEN", ""),
        live_send=live_send_enabled(env),
        http_post=http_post,
    )
    return WeatherService(JsonStore(store_path), adapter, welcome)


def run_event(event: str, store_path: Path, forecast: str = "", environ: dict[str, str] | None = None, http_post=None) -> list:
    service = build_service(store_path, environ, http_post)
    if event == "alerts":
        return []
    return service.run_schedule(event, forecast)
