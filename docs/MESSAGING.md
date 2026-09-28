# Portable messaging

The live agent still sends through Gamut iMessage. This module is a candidate interface for a later move. It does not send real texts.

## Current Gamut path, and what cannot move

Verified from this agent's tools and from messages the owner received:

- The integration provider name is `imessage`. Its advertised capability is `send_message` only. It does not list users or channels.
- Setup is: text `/setup` to Gamut's published iMessage setup number, receive a 6-digit code, and register the owner's phone with that code. Only one agent can hold the iMessage connection.
- A send to a bare phone number was accepted by the tool and then the integration status became `error`. The owner did not get that text.
- After the owner texted the line, Gamut created a thread ID. Sending to that thread ID stayed `active`, and the owner confirmed the forecast arrived in the same Messages conversation.
- The owner's phone showed the conversation under the name Weather, and the compose field in that thread said `RCS message`. Gamut's API still reported the provider as `imessage`. This export does not know which network hop produced that label.
- A contact card arrived during setup. It was not one of the forecast sends.

Inferred, not verified:

- The sender identity is Gamut's bridge, not a 10-digit number the owner controls. No portable account number, PIN, or carrier bill was available, so the current sender was not checked for porting.
- Apple iMessage threads and a Gamut thread ID cannot be imported into Twilio, Telnyx, or an RCS agent. Subscribers would have to text a new number and start a new thread.
- The owner's existing Weather thread can keep working on Gamut while a replacement is tested. Do not disconnect the live integration to try a port.

## Recommended replacement

Use Twilio programmable SMS on one US local 10DLC number, registered as a sole proprietor if there is no EIN. This is for a few invited people, two-way replies, and STOP opt-out. Do not buy the number until the owner asks.

RCS is feasible later on the same Twilio account, with SMS fallback, but US RCS registration asks for a business registration ID, a public opt-in policy, sample messages, and a use-case video. That is more process than this invite list needs. RCS would keep emoji forecasts in one bubble. SMS will split them into several segments because emoji uses the shorter UCS-2 segment size.

Telnyx is the cheaper per-segment alternative and passes 10DLC fees through. Twilio is the recommendation because its sole-proprietor path, inbound webhooks, and STOP handling are the most direct fit. Either provider still requires The Campaign Registry brand and campaign approval before reliable US delivery.

### Setup, not started

1. Create the provider account and complete identity verification.
2. Register a 10DLC brand. Sole proprietor if there is no EIN. Low-volume standard if there is an EIN.
3. Register one campaign for weather alerts and opted-in forecasts. Include STOP, HELP, and message frequency.
4. Buy or port a local number only after campaign approval. The Gamut sender is not a candidate for that port unless Gamut later proves the owner controls it.
5. Point the inbound webhook at the texter. Validate the provider signature.
6. Send one message to the owner's own phone with live sending explicitly enabled. Do not message the invite list until that test is accepted.

### Costs to budget

Checked against Twilio's US messaging price page (page dated 2026-05-18) and Twilio's A2P 10DLC fee pages. Carrier passthrough fees vary by carrier and were not copied as a single official rate.

- US long-code SMS: $0.0083 per segment outbound and inbound, plus carrier fees.
- Local number: from $1.15 per month.
- Sole proprietor registration on Twilio's fee table: about $4 one-time brand, $15 one-time campaign vetting, about $2 per month for the campaign.
- A forecast with emoji can be roughly 8 to 12 SMS segments. Four subscribers, two forecasts a week, and a handful of alerts is still only a few dollars to the low teens per month, plus the registration fees.
- RCS rich starts at the same $0.0083 headline rate on Twilio, but US onboarding fees are charged by the verifiers. Those dollar amounts were not captured here. Do not assume RCS is free to register.

Telnyx lists outbound SMS from $0.004 per part plus the same style of carrier and 10DLC passthrough fees, including a $4 sole-proprietor brand fee and a $2 monthly sole-proprietor campaign fee on its published 10DLC table. Number rental was not rechecked for this note.

Unregistered 10DLC traffic can be filtered and is billed at higher carrier rates. Register before any real test beyond the provider's own trial sandbox.

## What you would supply for a real-number test

Put these in the environment or a secret store, never in git:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM` in E.164
- A public webhook URL for inbound POSTs
- Confirmation that the 10DLC campaign is approved
- `GARLAND_ALLOW_LIVE_SEND=1` only for the one intentional test

The adapter in `texter/messaging.py` will not open a Twilio connection by itself. Tests use a recording transport and send nothing.

## What a move would change

Preserved if you cut over after subscribers text the new number:

- The forecast wording, spacing, alert emoji, Sunday and Wednesday schedule, alert deduplication, approved-name opt-in, and owner notice for strangers.

Not preserved:

- The current Weather thread, its contact card, and Gamut thread IDs.
- Delivery inside Apple's iMessage transcript if the phone was using that network. A new 10DLC thread is SMS, or RCS only after a separate brand registration and a new opt-in.
