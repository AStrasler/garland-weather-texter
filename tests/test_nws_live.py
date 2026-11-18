import json
import unittest
import urllib.request

from texter.safe_http import open_https_url


class NwsLiveTests(unittest.TestCase):
    def test_forecast_and_alerts_are_public(self):
        headers = {
            "User-Agent": "GarlandWeatherTexter/1.0 (export test)",
            "Accept": "application/geo+json",
        }
        forecast = urllib.request.Request(
            "https://api.weather.gov/gridpoints/FWD/95,110/forecast",
            headers=headers,
        )
        with open_https_url(forecast, allowed_hosts={"api.weather.gov"}, timeout=30) as resp:
            periods = json.load(resp)["properties"]["periods"]
        self.assertGreaterEqual(len(periods), 7)
        self.assertIn("temperature", periods[0])

        alerts = urllib.request.Request(
            "https://api.weather.gov/alerts/active?point=32.8804,-96.6496",
            headers=headers,
        )
        with open_https_url(alerts, allowed_hosts={"api.weather.gov"}, timeout=30) as resp:
            body = json.load(resp)
        self.assertIn("features", body)


if __name__ == "__main__":
    unittest.main()
