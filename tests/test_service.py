import tempfile
import unittest
from pathlib import Path

from texter.service import WeatherService
from texter.store import Approval, JsonStore, Subscriber
from texter.twilio import TwilioAdapter, compute_signature


WELCOME = "You're on the Garland weather texts."


class RecordingHttp:
    def __init__(self):
        self.calls = []

    def __call__(self, url, params, headers):
        self.calls.append({"url": url, "params": params})
        return 201, "SM-test"


def build(directory: Path, http: RecordingHttp | None = None, live: bool = True) -> tuple[WeatherService, RecordingHttp, Path]:
    http = http or RecordingHttp()
    path = directory / "store.json"
    store = JsonStore(path)
    store.data.owner_address = "+15550000000"
    store.data.approvals.append(Approval("Ada", "+15551110001"))
    store.data.subscribers.append(Subscriber("owner", "Owner", "+15550000000", status="active"))
    store.save()
    adapter = TwilioAdapter(
        from_number="+15557650000",
        account_sid="AC_test",
        auth_token="test-token",
        live_send=live,
        http_post=http,
    )
    return WeatherService(store, adapter, WELCOME), http, path


class ServiceTests(unittest.TestCase):
    def test_name_from_unapproved_number_does_not_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, http, _path = build(Path(tmp))
            service.handle_inbound("+15552220002", "Ada")
            self.assertEqual(http.calls[0]["params"]["To"], "+15550000000")
            self.assertIsNone(service.store.data.subscriber_by_address("+15552220002"))

    def test_owner_approved_number_and_name_receives_welcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, http, path = build(Path(tmp))
            service.handle_inbound("+15551110001", "Ada")
            reloaded = JsonStore(path)
            person = reloaded.data.subscriber_by_address("+15551110001")
            self.assertIsNotNone(person)
            self.assertEqual(person.status, "active")
            self.assertEqual(http.calls[0]["params"]["Body"], WELCOME)

    def test_stop_and_failed_alert_retries_only_the_missed_recipient(self):
        with tempfile.TemporaryDirectory() as tmp:
            http = RecordingHttp()
            service, _http, path = build(Path(tmp), http)
            service.handle_inbound("+15551110001", "Ada")
            service.store.data.subscribers.append(Subscriber("bea", "Bea", "+15551110002", status="active"))
            service.store.save()

            def flaky(url, params, headers):
                http.calls.append({"url": url, "params": params})
                if params["To"] == "+15551110002":
                    return 500, "no"
                return 201, "SM-ok"

            service.adapter.http_post = flaky
            service.deliver_alert("alert-1", "2026-09-28T00:00:00Z", "🚨 Alert")
            self.assertTrue(service.store.alert_received("alert-1", "+15551110001", "2026-09-28T00:00:00Z"))
            self.assertFalse(service.store.alert_received("alert-1", "+15551110002", "2026-09-28T00:00:00Z"))
            before = len(http.calls)
            service.retry_alert("alert-1", "2026-09-28T00:00:00Z", "🚨 Alert")
            retried = [call["params"]["To"] for call in http.calls[before:]]
            self.assertEqual(retried, ["+15551110002"])
            JsonStore(path)

    def test_one_unapproved_attempt_does_not_duplicate_thursday_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, http, _path = build(Path(tmp))
            service.handle_inbound("+15552220002", "Sam")
            service.handle_inbound("+15552220002", "Sam again")
            service.run_schedule("thursday_check")
            service.run_schedule("thursday_check")
            notices = [call for call in http.calls if call["params"]["To"] == "+15550000000"]
            self.assertEqual(len(notices), 1)

    def test_thursday_is_silent_when_nobody_unapproved_texted(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, http, _path = build(Path(tmp))
            service.run_schedule("thursday_check")
            self.assertEqual(http.calls, [])

    def test_webhook_rejects_bad_signature_and_live_switch_defaults_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, http, _path = build(Path(tmp), live=False)
            url = "https://example.test/webhook"
            params = {"From": "+15551110001", "Body": "Ada", "MessageSid": "SM1"}
            status, _results = service.accept_webhook(url, params, "bad")
            self.assertEqual(status, 403)
            self.assertEqual(http.calls, [])
            disabled = service.adapter.send_sms("+15551110001", "hello")
            self.assertFalse(disabled.accepted)
            self.assertEqual(http.calls, [])
            service.adapter.live_send = True
            signature = compute_signature("test-token", url, params)
            status, _results = service.accept_webhook(url, params, signature)
            self.assertEqual(status, 200)
            self.assertEqual(http.calls[0]["params"]["Body"], WELCOME)

    def test_scheduled_job_does_not_enable_live_send(self):
        from texter.jobs import run_event

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"
            store = JsonStore(path)
            store.data.owner_address = "+15550000000"
            store.data.subscribers.append(Subscriber("owner", "Owner", "+15550000000", status="active"))
            store.save()
            http = RecordingHttp()
            run_event("weekly", path, forecast="Sunday text", environ={}, http_post=http)
            self.assertEqual(http.calls, [])


if __name__ == "__main__":
    unittest.main()
