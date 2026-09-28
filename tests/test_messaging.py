import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from texter.messaging import (
    AlertLedger,
    Directory,
    Inbound,
    RecordingTransport,
    Subscriber,
    Texter,
    TwilioAdapter,
)


WELCOME = "You're on the Garland weather texts."
FORECAST = "Monday forecast."


def service() -> tuple[Texter, RecordingTransport, Directory]:
    transport = RecordingTransport()
    directory = Directory(approved_names={"Ada", "Bea", "Cam"}, owner_id="owner")
    directory.add(Subscriber("owner", "Owner", "+15550000000", status="active"))
    return Texter(transport, directory), transport, directory


class MessagingTests(unittest.TestCase):
    def test_approved_name_gets_welcome_and_later_forecast(self):
        texter, transport, _directory = service()
        texter.handle_inbound(Inbound("+15551110001", "Ada", "in-1"), WELCOME)
        texter.deliver_to_active(FORECAST, "weekly")
        kinds = [item.kind for item in transport.sent if item.to == "+15551110001"]
        self.assertEqual(kinds, ["welcome", "weekly"])

    def test_random_sender_notifies_owner_once_and_is_not_added(self):
        texter, transport, directory = service()
        texter.handle_inbound(Inbound("+15552220002", "Sam", "in-2"), WELCOME)
        texter.handle_inbound(Inbound("+15552220002", "hello again", "in-3"), WELCOME)
        notices = [item for item in transport.sent if item.kind == "owner_notice"]
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].to, "+15550000000")
        self.assertIsNone(directory.by_address("+15552220002"))

    def test_stop_opts_out_and_blocks_scheduled_delivery(self):
        texter, transport, _directory = service()
        texter.handle_inbound(Inbound("+15551110001", "Bea", "in-4"), WELCOME)
        texter.handle_inbound(Inbound("+15551110001", "STOP", "in-5"), WELCOME)
        texter.run_schedule("weekly", FORECAST)
        self.assertFalse(any(item.to == "+15551110001" and item.kind == "weekly" for item in transport.sent))
        self.assertTrue(any(item.kind == "opt_out" for item in transport.sent))

    def test_alert_is_not_sent_twice(self):
        texter, transport, _directory = service()
        texter.handle_inbound(Inbound("+15551110001", "Cam", "in-6"), WELCOME)
        first = texter.deliver_alert("alert-1", "2026-09-28T00:00:00Z", "🚨 Air Quality Alert")
        second = texter.deliver_alert("alert-1", "2026-09-28T00:00:00Z", "🚨 Air Quality Alert")
        updated = texter.deliver_alert("alert-1", "2026-09-28T01:00:00Z", "🚨 Air Quality Alert updated")
        to_subscriber = [item for item in transport.sent if item.to == "+15551110001" and item.kind == "alert"]
        self.assertEqual(len(first), 2)
        self.assertEqual(second, [])
        self.assertEqual(len(updated), 2)
        self.assertEqual(len(to_subscriber), 2)

    def test_failed_delivery_does_not_mark_alert_sent(self):
        transport = RecordingTransport(fail_for={"+15551110001"})
        directory = Directory(approved_names={"Ada"})
        directory.add(Subscriber("k", "Ada", "+15551110001", status="active"))
        texter = Texter(transport, directory, AlertLedger())
        texter.deliver_alert("alert-2", "2026-09-28T00:00:00Z", "🚨 Tornado Warning")
        self.assertTrue(texter.ledger.is_new("alert-2", "2026-09-28T00:00:00Z"))

    def test_thursday_check_is_silent_without_a_random_join(self):
        texter, transport, _directory = service()
        self.assertEqual(texter.run_schedule("thursday_check", "", datetime(2026, 10, 1, 15, tzinfo=ZoneInfo("America/Chicago"))), [])
        self.assertEqual(transport.sent, [])

    def test_thursday_check_reminds_owner_after_random_join(self):
        texter, transport, _directory = service()
        texter.handle_inbound(Inbound("+15553330003", "Pat", "in-7"), WELCOME)
        before = len(transport.sent)
        texter.run_schedule("thursday_check", "")
        self.assertGreater(len(transport.sent), before)
        self.assertEqual(transport.sent[-1].kind, "owner_notice")

    def test_twilio_adapter_parses_webhook_and_does_not_call_network(self):
        transport = RecordingTransport()
        adapter = TwilioAdapter("+15557654321", transport)
        inbound = adapter.parse_webhook({"From": "+15551110001", "Body": "Ada", "MessageSid": "SM123"})
        self.assertEqual(inbound.sender, "+15551110001")
        result = adapter.send_sms("+15551110001", "forecast", "weekly")
        self.assertTrue(result.accepted)
        self.assertEqual(transport.sent[0].body, "forecast")
        refused = adapter.send_sms("not-a-number", "forecast")
        self.assertFalse(refused.accepted)


if __name__ == "__main__":
    unittest.main()
