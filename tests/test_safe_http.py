import subprocess
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

from texter.safe_http import NoRedirectHandler, open_https_url, validate_https_url


class SafeHttpTests(unittest.TestCase):
    def test_accepts_only_explicit_https_provider_hosts(self):
        url = "https://api.weather.gov/alerts/active?point=32.8,-96.6"
        self.assertEqual(validate_https_url(url, allowed_hosts={"api.weather.gov"}), url)

    def test_rejects_unsafe_schemes_hosts_credentials_ports_and_fragments(self):
        unsafe = (
            "file:///etc/passwd",
            "http://api.weather.gov/alerts",
            "https://api.weather.gov.evil.test/alerts",
            "https://api.weather.gov@evil.test/alerts",
            "https://user@api.weather.gov/alerts",
            "https://api.weather.gov:8443/alerts",
            "https://api.weather.gov./alerts",
            "https://api.weather.gov/alerts#fragment",
            "https://[invalid/alerts",
        )
        for url in unsafe:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_https_url(url, allowed_hosts={"api.weather.gov"})

    def test_subdomains_are_allowed_only_when_explicit(self):
        url = "https://www.fox4news.com/weather"
        with self.assertRaises(ValueError):
            validate_https_url(url, allowed_hosts={"fox4news.com"})
        self.assertEqual(
            validate_https_url(url, allowed_hosts={"fox4news.com"}, allow_subdomains=True),
            url,
        )

    def test_rejects_redirects(self):
        request = urllib.request.Request("https://api.weather.gov/alerts")
        handler = NoRedirectHandler()
        with self.assertRaises(urllib.error.URLError):
            handler.redirect_request(
                request, None, 302, "Found", {}, "https://evil.test/collect"
            )

    def test_invalid_host_is_rejected_before_opening_network(self):
        with patch("urllib.request.build_opener") as build_opener:
            with self.assertRaises(ValueError):
                open_https_url(
                    "https://evil.test/collect",
                    allowed_hosts={"api.weather.gov"},
                    timeout=2,
                )
            build_opener.assert_not_called()

    def test_approved_request_uses_redirect_blocking_opener_and_timeout(self):
        response = Mock()
        opener = Mock()
        opener.open.return_value = response
        request = urllib.request.Request("https://api.weather.gov/alerts")
        with patch("urllib.request.build_opener", return_value=opener) as build_opener:
            result = open_https_url(
                request, allowed_hosts={"api.weather.gov"}, timeout=7
            )
        self.assertIs(result, response)
        build_opener.assert_called_once()
        self.assertIsInstance(build_opener.call_args.args[0], NoRedirectHandler)
        opener.open.assert_called_once_with(request, timeout=7)

    def test_weather_scripts_keep_standalone_imports(self):
        script_dir = Path(__file__).resolve().parents[1] / "texter"
        code = (
            "import importlib, sys; "
            "sys.path[0] = sys.argv[1]; "
            "importlib.import_module(sys.argv[2])"
        )
        for module in ("alerts", "sms_forecast"):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-c", code, str(script_dir), module],
                    cwd=script_dir.parent,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
