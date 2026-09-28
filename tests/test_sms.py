import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "texter"))

import sms_forecast as sms


TZ = ZoneInfo("America/Chicago")


def day(iso: str, high: int, low: int, pop: int, description: str = "cloudy") -> dict:
    moment = datetime.fromisoformat(iso).replace(tzinfo=TZ)
    return {
        "date": moment,
        "high": high,
        "low": low,
        "pop": pop,
        "humidity": 40,
        "wind": 5,
        "condition": "",
        "description": description,
        "near_term": True,
    }


class FormatTests(unittest.TestCase):
    def test_blank_line_between_days_and_alert_emoji(self):
        text = sms.render([day("2026-09-28T00:00:00", 93, 73, 20, "mostly sunny")], "", ["Air Quality Alert"])
        self.assertIn("\n\n", text)
        self.assertIn("🚨 Alerts: Air Quality Alert.", text)
        self.assertNotIn("Test", text)
        self.assertNotIn("NOAA only", text)

    def test_old_news_is_not_today(self):
        today = datetime(2026, 9, 27, 22, 0, tzinfo=TZ)
        self.assertFalse(sms.page_is_today("Published September 22, 2026", today))
        self.assertTrue(sms.page_is_today("Published September 27, 2026", today))

    def test_west_of_i35_does_not_override_a_low_nws_chance(self):
        days = [day("2026-09-28T00:00:00", 93, 73, 24, "slight chance showers and thunderstorms")]
        sms.apply_news(days, "storms remain west of I-35")
        self.assertFalse(days[0].get("mostly_dry"))
        self.assertEqual(days[0]["pop"], 24)

    def test_west_of_i35_caps_a_high_near_term_chance(self):
        days = [day("2026-09-28T00:00:00", 91, 71, 90, "thunderstorm")]
        sms.apply_news(days, "storms remain west of I-35")
        self.assertTrue(days[0]["mostly_dry"])
        self.assertEqual(days[0]["pop"], 30)

    def test_seven_days_fills_from_backup(self):
        now = datetime(2026, 9, 27, 22, 0, tzinfo=TZ)
        primary = [day("2026-09-28T00:00:00", 91, 71, 20)]
        start = datetime(2026, 9, 28, tzinfo=TZ)
        backup = [
            day((start + timedelta(days=offset)).strftime("%Y-%m-%dT00:00:00"), 80, 60, 10)
            for offset in range(7)
        ]
        chosen = sms.seven_days(primary, backup, now)
        self.assertEqual(len(chosen), 7)
        self.assertEqual(chosen[0]["high"], 91)


if __name__ == "__main__":
    unittest.main()
