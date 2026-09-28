# Garland weather texter

Builds the Garland, Texas 75041 forecast text and the alert check used by the live Gamut agent. The live agent, its iMessage connection, and its schedules are unchanged by this repository.

## What runs on a schedule

All times are America/Chicago.

| When | What |
| --- | --- |
| Sunday 7:00 p.m. | Seven-day forecast text |
| Wednesday 7:00 a.m. | Same format, midweek update, no extra title |
| Every 15 minutes | New or updated NWS alerts only |
| Thursday 3:00 p.m. | Text the owner only if someone who was not approved tried to join |

Forecast and alert rules are in [docs/RULES.md](docs/RULES.md). What Gamut does for texting, scheduling, and replies is in [docs/GAMUT.md](docs/GAMUT.md).

## What works without Gamut

These use public NOAA endpoints and the Python standard library:

```bash
cp examples/config.example.json texter/config.json
python3 texter/sms_forecast.py --news-file examples/news.example.txt
python3 texter/alerts.py
```

`sms_forecast.py` prints the text and does not send it. `alerts.py` prints `STATUS none` or `STATUS new`. Marking an alert sent is local state in `sent-alerts.json`, which is gitignored.

A same-day news file is optional. If its date is not today in America/Chicago, it is ignored.

## What still needs Gamut or another texting service

- Delivering the Sunday, Wednesday, and alert texts
- Noticing that someone texted the line
- Mapping that thread to a chat ID
- The Thursday 3:00 p.m. owner reminder
- Keeping the iMessage connection alive

No texting provider is selected or configured here. Do not point the live agent at a different provider.

## Setup

Python 3.11 or newer. No pip packages.

```bash
cp examples/config.example.json texter/config.json
cp examples/recipients.example.json texter/recipients.json
cp examples/approved.example.json texter/approved.json
python3 -m unittest tests/test_sms.py
```

On Gamut, the live copies stay in the agent skill directory. This repo is the portable description of that behavior. Copy templates and examples. Do not copy a live `recipients.json`, `approved.json`, `.env`, or phone number into git.

Secrets, if a future source needs one, belong in the environment or the agent secret store. Never commit them.

## Message template

`templates/welcome.txt` is the exact notice for a person the owner has already approved, after that person texts the line.

The forecast body has no welcome and no test label. Active alerts are the last block and start with 🚨.

## Tests

```bash
python3 -m unittest tests/test_sms.py
python3 -m unittest tests/test_nws_live.py
```

The live test only reads the public National Weather Service API. It does not send a message.
