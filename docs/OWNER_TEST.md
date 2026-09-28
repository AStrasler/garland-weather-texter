# Owner-only Twilio test

This sends one NOAA forecast to a single verified phone. It does not add subscribers and does not start a schedule. The live Gamut Weather agent is not part of this test.

Live send stays off until `GARLAND_ALLOW_LIVE_SEND` is exactly `1`.

## Enter the secrets

On the agent home, open Secrets. Add each name and value there. Do not paste them into chat and do not commit them.

| Name | Value |
| --- | --- |
| `TWILIO_ACCOUNT_SID` | Account SID from the Twilio console |
| `TWILIO_AUTH_TOKEN` | Auth token from the Twilio console |
| `TWILIO_FROM` | Trial sender, E.164, such as `+15551230000` |
| `TWILIO_TO` | The one Twilio-verified phone, E.164 |

When you want the one test to run, add:

| Name | Value |
| --- | --- |
| `GARLAND_ALLOW_LIVE_SEND` | `1` |

Then say the switch is on. The test script sends only to `TWILIO_TO`. It refuses a missing number, a list of numbers, and a disabled switch.

For a local checkout, put the same names in a gitignored `.env`. The examples in this repo do not contain real values.

## Run

```bash
PYTHONPATH=. python3 texter/owner_test.py
```

A Twilio trial account prefixes the message and can deliver only to numbers verified in that trial. This does not register 10DLC and does not buy a number.
