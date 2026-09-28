#!/usr/bin/env python3
"""Build a short Garland forecast from OpenWeather plus same-day local TV text."""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

CONFIG_PATH = Path(__file__).with_name("config.json")
USER_AGENT = "GamutWeatherAgent/1.0 (Garland forecast)"
TZ = ZoneInfo("America/Chicago")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SOURCE_PAGES = (
    "https://www.fox4news.com/weather",
    "https://www.wfaa.com/weather",
    "https://www.nbcdfw.com/weather/",
)


def load_env() -> None:
    path = Path("/workspace/.env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", "replace")


def get_json(url: str) -> dict:
    return json.loads(get_text(url))


def local_today(now: datetime | None = None) -> datetime:
    return (now or datetime.now(TZ)).astimezone(TZ)


def date_labels(day: datetime) -> list[str]:
    return [
        day.strftime("%Y-%m-%d"),
        day.strftime("%B %-d, %Y"),
        day.strftime("%b. %-d"),
        day.strftime("%B %-d"),
    ]


def page_is_today(text: str, today: datetime) -> bool:
    lowered = text.lower()
    return any(label.lower() in lowered for label in date_labels(today))


def visible_text(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_news(today: datetime) -> str:
    chunks = []
    seen = set()
    for page in SOURCE_PAGES:
        try:
            html = get_text(page)
        except Exception:
            continue
        if page_is_today(html, today):
            chunks.append(visible_text(html)[:4000])
        for href in re.findall(r'href="(https://[^"]+)"', html):
            if href in seen or not any(host in href for host in ("fox4news.com", "wfaa.com", "nbcdfw.com")):
                continue
            if "/weather" not in href and "/article/weather" not in href:
                continue
            seen.add(href)
            if len(seen) > 8:
                break
            try:
                article = get_text(href)
            except Exception:
                continue
            if page_is_today(article):
                chunks.append(visible_text(article)[:5000])
    return "\n".join(chunks)


def openweather_days(config: dict, now: datetime) -> list[dict]:
    key = os.environ.get("OPENWEATHER_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENWEATHER_API_KEY is missing")
    url = "https://api.openweathermap.org/data/2.5/forecast?" + urllib.parse.urlencode(
        {
            "lat": config["latitude"],
            "lon": config["longitude"],
            "units": "imperial",
            "appid": key,
        }
    )
    data = get_json(url)
    grouped: dict[str, list] = {}
    for item in data.get("list") or []:
        local = datetime.fromtimestamp(item["dt"], TZ)
        grouped.setdefault(local.strftime("%Y-%m-%d"), []).append((local, item))
    days = []
    for key_day, slots in grouped.items():
        highs = [item["main"]["temp"] for local, item in slots if 11 <= local.hour <= 18]
        lows = [item["main"]["temp"] for local, item in slots if local.hour <= 8]
        if not highs or not lows:
            continue
        hot = max(slots, key=lambda pair: pair[1]["main"]["temp"] if 11 <= pair[0].hour <= 18 else -999)
        humidity = hot[1]["main"].get("humidity") or 0
        wind = max(item.get("wind", {}).get("speed") or 0 for _, item in slots)
        pop = max(int(round((item.get("pop") or 0) * 100)) for _, item in slots)
        weather = (hot[1].get("weather") or [{}])[0]
        moment = datetime.strptime(key_day, "%Y-%m-%d").replace(tzinfo=TZ)
        days.append(
            {
                "date": moment,
                "high": round(max(highs)),
                "low": round(min(lows)),
                "pop": pop,
                "humidity": humidity,
                "wind": wind,
                "condition": weather.get("main") or "",
                "description": weather.get("description") or "",
                "near_term": moment < now + timedelta(hours=48),
            }
        )
    return days


def nws_days(config: dict, now: datetime) -> list[dict]:
    url = config.get("nws_forecast_url")
    if not url:
        return []
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        periods = json.load(resp)["properties"]["periods"]
    grouped: dict[str, dict] = {}
    for period in periods:
        start = datetime.fromisoformat(period["startTime"]).astimezone(TZ)
        day = grouped.setdefault(
            start.strftime("%Y-%m-%d"),
            {
                "date": start.replace(hour=0, minute=0, second=0, microsecond=0),
                "high": None,
                "low": None,
                "pop": None,
                "humidity": 0,
                "wind": 0,
                "condition": "",
                "description": "",
                "near_term": start < now + timedelta(hours=48),
            },
        )
        pop = (period.get("probabilityOfPrecipitation") or {}).get("value")
        if pop is not None and (day["pop"] is None or pop > day["pop"]):
            day["pop"] = int(round(pop))
        detail = (period.get("detailedForecast") or "").lower()
        if "heat index" in detail:
            day["heat"] = True
        gust = re.search(r"gusts as high as (\d+)", detail)
        if gust:
            day["wind"] = max(day["wind"], int(gust.group(1)))
        if period.get("isDaytime"):
            day["high"] = period.get("temperature")
            day["description"] = (period.get("shortForecast") or "").lower()
        else:
            day["low"] = period.get("temperature")
            if not day["description"]:
                day["description"] = (period.get("shortForecast") or "").lower()
    fill_missing_lows(config, grouped, now)
    ready = []
    for day in grouped.values():
        if day["high"] is None or day["low"] is None:
            continue
        day["pop"] = 0 if day["pop"] is None else day["pop"]
        ready.append(day)
    return ready


def fill_missing_lows(config: dict, grouped: dict[str, dict], now: datetime) -> None:
    url = config.get("nws_forecast_url", "").removesuffix("/forecast")
    if not url:
        return
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            values = json.load(resp)["properties"]["minTemperature"]["values"]
    except Exception:
        return
    for item in values:
        start = datetime.fromisoformat(item["validTime"].split("/")[0]).astimezone(TZ)
        if start.hour < 12:
            continue
        key = start.strftime("%Y-%m-%d")
        day = grouped.get(key)
        if day and day["low"] is None:
            day["low"] = round(item["value"] * 9 / 5 + 32)
            day["near_term"] = start < now + timedelta(hours=48)


def seven_days(primary: list[dict], backup: list[dict], now: datetime) -> list[dict]:
    start = now.date()
    if now.hour >= 18 and not any(day["date"].date() == start and day.get("high") for day in primary):
        start = start + timedelta(days=1)
    by_date = {day["date"].date(): day for day in primary}
    for day in backup:
        by_date.setdefault(day["date"].date(), day)
    chosen = []
    for offset in range(7):
        key = start + timedelta(days=offset)
        if key in by_date:
            chosen.append(by_date[key])
    return chosen


def west_of_i35(news: str) -> bool:
    text = news.lower()
    west = "west of i-35" in text or "west of interstate 35" in text or "west and northwest" in text
    east = "east of i-35" in text or "garland" in text or "eastern metro" in text
    return west and not east


def named_hazard_days(news: str) -> set[str]:
    text = news.lower()
    found = set()
    for name in WEEKDAYS:
        window = text
        for match in re.finditer(name, text):
            window = text[max(0, match.start() - 80) : match.end() + 80]
            if any(word in window for word in ("storm", "heavy rain", "flood", "downpour")):
                found.add(name)
                if "flood" in window:
                    found.add(name + ":flood")
                break
        if "wednesday through friday" in text and name in ("wednesday", "thursday", "friday"):
            found.add(name)
            if "flood" in text:
                found.add(name + ":flood")
    return found


def sky_for(day: dict) -> str:
    pop = day["pop"]
    desc = day["description"]
    if day.get("mostly_dry"):
        return "Mostly dry"
    if "slight" in desc and pop < 40:
        return "Slight storm chance"
    if day.get("hazard") and pop >= 50:
        if day.get("flood"):
            return "Storms/flood"
        return "Heavy rain" if pop >= 70 else "Storms likely"
    if pop >= 60 or ("thunder" in desc and pop >= 50):
        return "Storms likely"
    if pop >= 40 or "rain" in desc:
        return "Rain likely"
    if "overcast" in desc:
        return "Cloudy"
    if "cloud" in desc or "sunny" in desc:
        return "Partly cloudy" if "partly" in desc else "Mostly sunny"
    return "Clear"


def emojis_for(day: dict, sky: str) -> str:
    icons = []
    hot = day.get("heat") or day["high"] >= 95 or (day["high"] >= 90 and day["humidity"] >= 60)
    if hot:
        icons.append("🥵")
    if day["wind"] >= 15:
        icons.append("💨")
    if "slight" in sky.lower():
        icons.append("⛅")
    elif "flood" in sky.lower() or "storm" in sky.lower():
        icons.append("⛈️")
    elif "heavy" in sky.lower() or day["pop"] >= 70:
        icons.append("🌧️" if "heavy" in sky.lower() else "⛈️")
    elif "storm" in sky.lower():
        icons.append("⛈️")
    elif day["pop"] >= 40 or "rain" in sky.lower():
        icons.append("🌧️")
    elif day.get("mostly_dry") and "cloud" in day["description"]:
        icons.append("⛅")
    elif "cloudy" in sky.lower() and "partly" not in sky.lower():
        icons.append("☁️")
    elif "partly" in sky.lower():
        icons.append("⛅")
    elif not icons:
        icons.append("☀️")
    return "".join(dict.fromkeys(icons))


def insight(days: list[dict], news: str) -> str:
    if not days:
        return "Forecast data is unavailable."
    first, last = days[0], days[-1]
    wet = [day for day in days if day["pop"] >= 50 or day.get("hazard")]
    if wet and last["high"] + 5 < first["high"]:
        start = wet[0]["date"].strftime("%a")
        band = "the 70s" if last["high"] < 80 else f"the {last['high'] // 10 * 10}s"
        return f"Hot early, then storms from {start} and a cooldown into {band} by {last['date'].strftime('%a')}."
    if wet:
        return f"Storm chances build {wet[0]['date'].strftime('%a')}, with highs {min(d['high'] for d in days)}–{max(d['high'] for d in days)}°F."
    if "west of i-35" in news.lower():
        return "Warm and mostly dry in Garland, with the nearer storms staying west of I-35."
    return f"Highs {min(d['high'] for d in days)}–{max(d['high'] for d in days)}°F through {last['date'].strftime('%a')}."


def active_alerts(config: dict) -> list[str]:
    url = (
        "https://api.weather.gov/alerts/active?point="
        f"{config['latitude']},{config['longitude']}"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except Exception:
        return []
    seen = set()
    alerts = []
    for feature in data.get("features") or []:
        event = (feature.get("properties") or {}).get("event") or "Weather alert"
        if event in seen:
            continue
        seen.add(event)
        alerts.append(event)
    return alerts[:3]


def render(days: list[dict], news: str, alerts: list[str]) -> str:
    blocks = [insight(days, news)]
    for day in days[:7]:
        sky = sky_for(day)
        label = day["date"].strftime("%a")
        blocks.append(
            f"{emojis_for(day, sky)} {label}: {sky}.\n"
            f"High: {day['high']}°F, Low: {day['low']}°F. Rain: {day['pop']}%."
        )
    blocks.append(
        "🚨 Alerts: " + "; ".join(alerts) + "." if alerts else "🚨 No active weather alerts."
    )
    return "\n\n".join(blocks)


def apply_news(days: list[dict], news: str) -> None:
    hazards = named_hazard_days(news) if news else set()
    west = west_of_i35(news) if news else False
    for day in days:
        name = day["date"].strftime("%A").lower()
        if name in hazards:
            day["hazard"] = True
            day["flood"] = f"{name}:flood" in hazards
        if day["near_term"] and west and day["pop"] > 40:
            day["mostly_dry"] = True
            day["pop"] = min(day["pop"], 30)
            day["hazard"] = False


def main() -> int:
    load_env()
    config = json.loads(CONFIG_PATH.read_text())
    now = local_today()
    news = ""
    if "--news-file" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--news-file") + 1])
        raw = path.read_text()
        news = raw if page_is_today(raw, now) else ""
    else:
        news = fetch_news(now)
    days = seven_days([], nws_days(config, now), now)
    apply_news(days, news)
    sys.stdout.write(render(days, news, active_alerts(config)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
