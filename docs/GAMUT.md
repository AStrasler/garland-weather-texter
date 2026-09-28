# What Gamut provides

This compiler can build a forecast without Gamut. Sending it, receiving a reply, and running the clocks are Gamut features in the live agent. This export does not replace those features and does not change the live schedules.

## Texting

Gamut connects the agent to iMessage. That is not carrier SMS, email, Slack, or Telegram.

What Gamut does:

- Holds the iMessage connection for this agent. The agent never sees the provider credential.
- Accepts a verified phone number after the owner texts `/setup` to Gamut's iMessage setup number and supplies the 6-digit code.
- Delivers a proactive text when the agent calls `send_chat_message` with the integration ID and the thread `chat_id`.
- Starts a new agent session when someone texts the line. The session's reply is delivered back automatically. A second `send_chat_message` in that same session would post twice.
- Lists existing threads. A thread appears after the person messages the bot. A bare phone number is not a reliable destination. Using one marked the live integration as an error and the text did not arrive.

What Gamut does not do:

- It does not fetch NOAA or local TV forecasts.
- It does not decide who may join.
- It does not provide a public SMS API or a short code for this agent.
- It cannot text a number that has never messaged the line.

A replacement texter would need a two-way channel that can send to an existing conversation and can notify the compiler when a new person texts in.

## Scheduling

Gamut runs two different clocks.

Recurring jobs use cron in America/Chicago and start a new session with a self-contained prompt. The live jobs are:

- `0 19 * * 0` Sunday 7:00 p.m. weekly text
- `0 7 * * 3` Wednesday 7:00 a.m. midweek update
- `*/15 * * * *` alert check

The Thursday 3:00 p.m. new-subscriber reminder is not one of those crons. It resumes the same conversation. That session can see whether an unapproved person texted. A brand-new cron session would not have that conversation unless the rule is also written down, which is why it is in `docs/RULES.md`.

Gamut does not run the forecast script on its own. The scheduled session has to run the script and then send the output.

## Receiving replies

An incoming iMessage is how opt-in is observed. Gamut delivers the message text and a chat ID to a new agent session. Matching that text to an approved name, updating `recipients.json`, and sending the welcome are agent rules, not a Gamut form.

Do not treat a contact card from setup as a forecast or as a join.
