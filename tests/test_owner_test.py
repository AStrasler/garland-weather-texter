import json
import unittest

from texter.owner_test import run_owner_test


class OwnerTestTests(unittest.TestCase):
    def test_switch_off_sends_nothing(self):
        calls = []

        def post(url, params, headers):
            calls.append(params)
            return 201, json.dumps({"sid": "SM1", "status": "queued"})

        outcome = run_owner_test(
            {
                "TWILIO_ACCOUNT_SID": "AC_test",
                "TWILIO_AUTH_TOKEN": "token",
                "TWILIO_FROM": "+15557650000",
                "TWILIO_TO": "+15551110001",
            },
            http_post=post,
        )
        self.assertFalse(outcome["sent"])
        self.assertEqual(outcome["reason"], "live send disabled")
        self.assertEqual(calls, [])

    def test_one_verified_number_only(self):
        calls = []

        def post(url, params, headers):
            calls.append(params["To"])
            return 201, json.dumps({"sid": "SM123", "status": "queued"})

        outcome = run_owner_test(
            {
                "GARLAND_ALLOW_LIVE_SEND": "1",
                "TWILIO_ACCOUNT_SID": "AC_test",
                "TWILIO_AUTH_TOKEN": "token",
                "TWILIO_FROM": "+15557650000",
                "TWILIO_TO": "+15551110001",
                "GARLAND_TEST_BODY": "forecast",
            },
            http_post=post,
        )
        self.assertTrue(outcome["sent"])
        self.assertEqual(calls, ["+15551110001"])
        self.assertEqual(outcome["sid"], "SM123")

    def test_refuses_a_list_of_numbers(self):
        with self.assertRaises(SystemExit):
            run_owner_test(
                {
                    "GARLAND_ALLOW_LIVE_SEND": "1",
                    "TWILIO_ACCOUNT_SID": "AC_test",
                    "TWILIO_AUTH_TOKEN": "token",
                    "TWILIO_FROM": "+15557650000",
                    "TWILIO_TO": "+15551110001 +15552220002",
                    "GARLAND_TEST_BODY": "forecast",
                }
            )
