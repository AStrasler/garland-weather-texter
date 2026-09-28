#!/usr/bin/env python3
"""Print new NWS alerts for the configured point. Mark them sent after delivery."""

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CONFIG_PATH = Path(__file__).with_name("config.json")
STATE_PATH = Path(__file__).with_name("sent-alerts.json")
USER_AGENT = "GamutWeatherAgent/1.0 (alert check for Garland TX)"


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    with path.open() as f:
        return json.load(f)


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def format_when(value: str | None, tz: ZoneInfo) -> str | None:
    moment = parse_time(value)
    if moment is None:
        return None
    local = moment.astimezone(tz)
    return local.strftime("%a %-m/%-d %-I:%M%p").replace("AM", "am").replace("PM", "pm") + " CT"


def clean_text(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.isupper() and len(stripped) <= 12:
            continue
        lines.append(stripped)
    cleaned = " ".join(lines)
    if len(cleaned) > 420:
        cleaned = cleaned[:417].rsplit(" ", 1)[0] + "..."
    return cleaned


def alert_message(props: dict, tz: ZoneInfo) -> str:
    event = props.get("event") or "Weather alert"
    when = format_when(props.get("ends") or props.get("expires"), tz)
    area = props.get("areaDesc") or "Garland area"
    instruction = clean_text(props.get("instruction") or "")
    description = clean_text(props.get("description") or "")
    lines = [f"NWS alert: {event}"]
    meta = area
    if when:
        meta += f". Until {when}"
    lines.append(meta + ".")
    if instruction:
        lines.append(instruction)
    elif description:
        lines.append(description)
    return "\n".join(lines)


def active_alerts(config: dict) -> list[dict]:
    url = (
        "https://api.weather.gov/alerts/active?point="
        f"{config['latitude']},{config['longitude']}"
    )
    data = get_json(url)
    alerts = []
    for feature in data.get("features") or []:
        props = feature.get("properties") or {}
        alert_id = feature.get("id") or props.get("id")
        if not alert_id:
            continue
        updated = props.get("updated") or props.get("sent") or ""
        alerts.append({"id": alert_id, "updated": updated, "props": props})
    return alerts


def prune(state: dict) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    sent = state.setdefault("sent", {})
    stale = []
    for alert_id, info in sent.items():
        marked = parse_time(info.get("marked_at"))
        if marked and marked < cutoff:
            stale.append(alert_id)
    for alert_id in stale:
        del sent[alert_id]


def is_new(state: dict, alert: dict) -> bool:
    previous = state.get("sent", {}).get(alert["id"])
    if not previous:
        return True
    old = parse_time(previous.get("updated"))
    new = parse_time(alert["updated"])
    if old and new:
        return new > old
    return previous.get("updated") != alert["updated"]


def mark(alert_id: str, updated: str) -> None:
    state = load_json(STATE_PATH, {"sent": {}})
    prune(state)
    state["sent"][alert_id] = {
        "updated": updated,
        "marked_at": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def seed_current() -> None:
    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"sent": {}})
    now = datetime.now(timezone.utc).isoformat()
    for alert in active_alerts(config):
        state["sent"][alert["id"]] = {"updated": alert["updated"], "marked_at": now}
    save_state(state)
    print(f"SEEDED {len(state['sent'])}")


def check() -> int:
    config = load_json(CONFIG_PATH, {})
    tz = ZoneInfo(config["timezone"])
    state = load_json(STATE_PATH, {"sent": {}})
    prune(state)
    save_state(state)
    fresh = [alert for alert in active_alerts(config) if is_new(state, alert)]
    if not fresh:
        print("STATUS none")
        return 0
    print("STATUS new")
    print(f"COUNT {len(fresh)}")
    for alert in fresh:
        print("---")
        print(f"ID {alert['id']}")
        print(f"UPDATED {alert['updated']}")
        print("MESSAGE")
        print(alert_message(alert["props"], tz))
    return 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--seed-current":
        seed_current()
        return 0
    if len(sys.argv) == 4 and sys.argv[1] == "--mark":
        mark(sys.argv[2], sys.argv[3])
        print("MARKED")
        return 0
    if len(sys.argv) != 1:
        print("Usage: alerts.py [--seed-current | --mark ID UPDATED]", file=sys.stderr)
        return 2
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
