import unittest
import http.client
import urllib.error
import urllib.request
from datetime import datetime
from unittest.mock import patch

from texter import sms_forecast as forecast


class NewsSecurityTests(unittest.TestCase):
    def test_allowed_hosts_and_subdomains(self):
        for url in ("https://fox4news.com/weather", "https://www.wfaa.com/weather", "https://weather.nbcdfw.com/weather?q=a", "https://www.wfaa.com:443/weather"):
            self.assertTrue(forecast.is_news_url(url), url)

    def test_spoofed_hosts_schemes_credentials_and_ports(self):
        for url in ("https://evil.test/weather?fox4news.com", "https://fox4news.com.evil.test/weather", "https://fox4news.com@evil.test/weather", "https://user@www.wfaa.com/weather", "http://wfaa.com/weather", "file:///weather/wfaa.com", "https://wfaa.com:8443/weather", "https://[invalid/weather"):
            self.assertFalse(forecast.is_news_url(url), url)
            with patch("urllib.request.build_opener") as opener:
                with self.assertRaises(urllib.error.URLError):
                    forecast.get_news_text(url)
                opener.assert_not_called()

    def test_redirects_are_checked_before_following(self):
        handler = forecast.NewsRedirectHandler()
        request = urllib.request.Request("https://www.wfaa.com/weather")
        for destination in ("https://evil.test/weather?wfaa.com", "http://wfaa.com/weather", "https://wfaa.com:8443/weather"):
            with self.assertRaises(urllib.error.URLError):
                handler.redirect_request(request, None, 302, "Found", {}, destination)
        allowed = handler.redirect_request(request, None, 302, "Found", {}, "https://www.nbcdfw.com/weather/today")
        self.assertEqual(allowed.full_url, "https://www.nbcdfw.com/weather/today")

    def test_news_fetch_filters_links_and_passes_the_day(self):
        today = datetime(2026, 11, 10, tzinfo=forecast.TZ)
        page = '<a href="https://evil.test/weather?wfaa.com">bad</a><a href="https://www.wfaa.com/weather/today">good</a>'
        with patch.object(forecast, "SOURCE_PAGES", ("https://www.wfaa.com/weather",)), \
                patch.object(forecast, "get_news_text", side_effect=[page, "dated news"]) as fetch, \
                patch.object(forecast, "page_is_today", side_effect=lambda text, day: text == "dated news") as same_day:
            self.assertEqual(forecast.fetch_news(today), "dated news")
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(fetch.call_args.args[0], "https://www.wfaa.com/weather/today")
            same_day.assert_any_call("dated news", today)

    def test_one_unavailable_publication_keeps_fallback_behavior(self):
        for error in (urllib.error.URLError("offline"), http.client.InvalidURL("bad path"), http.client.IncompleteRead(b"partial"), UnicodeError("unencoded URL")):
            with patch.object(forecast, "get_news_text", side_effect=error):
                self.assertEqual(forecast.fetch_news(datetime(2026, 11, 10, tzinfo=forecast.TZ)), "")
