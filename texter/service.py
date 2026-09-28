"""Invite, opt-out, schedules, and per-recipient alert delivery."""

from __future__ import annotations

from texter.messaging import Outbound, SendResult
from texter.store import Approval, JsonStore, Subscriber
from texter.twilio import TwilioAdapter

STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}
OPT_OUT_TEXT = "You are opted out of Garland weather texts. Text your name from this number to ask again."
WELCOME_KIND = "welcome"


class WeatherService:
    def __init__(self, store: JsonStore, adapter: TwilioAdapter, welcome: str):
        self.store = store
        self.adapter = adapter
        self.welcome = welcome

    def send(self, message: Outbound) -> SendResult:
        return self.adapter.send_sms(message.to, message.body, message.kind)

    def handle_inbound(self, sender: str, body: str) -> list[SendResult]:
        word = " ".join(body.strip().split())
        lowered = word.lower()
        person = self.store.data.subscriber_by_address(sender)
        if lowered in STOP_WORDS and person is not None:
            person.opted_out = True
            person.status = "opted_out"
            self.store.save()
            return [self.send(Outbound(sender, OPT_OUT_TEXT, "opt_out"))]
        approval = self.store.data.approval_for_address(sender)
        if approval is not None and lowered == approval.name.lower():
            return [self._activate(approval, sender)]
        if approval is None and lowered not in STOP_WORDS:
            return self._notice_owner_once(sender)
        return []

    def _activate(self, approval: Approval, sender: str) -> SendResult:
        person = self.store.data.subscriber_by_address(sender)
        if person is None:
            person = Subscriber(
                subscriber_id=f"sub-{approval.name.lower()}",
                display_name=approval.name,
                address=sender,
                status="active",
            )
            self.store.data.subscribers.append(person)
        else:
            person.display_name = approval.name
            person.status = "active"
            person.opted_out = False
        self.store.save()
        return self.send(Outbound(sender, self.welcome, WELCOME_KIND))

    def _notice_owner_once(self, sender: str) -> list[SendResult]:
        if sender not in self.store.data.unapproved_attempts:
            self.store.data.unapproved_attempts.append(sender)
            self.store.save()
        if sender in self.store.data.owner_notified:
            return []
        owner = self.store.data.owner_address
        if not owner:
            return []
        result = self.send(
            Outbound(
                owner,
                "Someone who is not approved for this number texted the weather line. They were not added.",
                "owner_notice",
            )
        )
        if result.accepted:
            self.store.data.owner_notified.append(sender)
            self.store.save()
        return [result]

    def deliver(self, body: str, kind: str) -> list[SendResult]:
        return [self.send(Outbound(person.address, body, kind)) for person in self.store.data.active()]

    def deliver_alert(self, alert_id: str, updated: str, body: str) -> list[SendResult]:
        results = []
        for person in self.store.data.active():
            if self.store.alert_received(alert_id, person.address, updated):
                continue
            result = self.send(Outbound(person.address, body, "alert"))
            results.append(result)
            if result.accepted:
                self.store.mark_alert(alert_id, person.address, updated)
        return results

    def retry_alert(self, alert_id: str, updated: str, body: str) -> list[SendResult]:
        return self.deliver_alert(alert_id, updated, body)

    def run_schedule(self, event: str, forecast: str = "") -> list[SendResult]:
        if event in {"weekly", "midweek"}:
            return self.deliver(forecast, event)
        if event == "thursday_check":
            pending = [
                sender
                for sender in self.store.data.unapproved_attempts
                if sender not in self.store.data.owner_notified
            ]
            if not pending or not self.store.data.owner_address:
                return []
            result = self.send(
                Outbound(
                    self.store.data.owner_address,
                    "An unapproved person tried to join the Garland weather texts. They were not added.",
                    "owner_notice",
                )
            )
            if result.accepted:
                self.store.data.owner_notified.extend(pending)
                self.store.save()
            return [result]
        return []

    def accept_webhook(self, url: str, params: dict[str, str], signature: str) -> tuple[int, list[SendResult]]:
        inbound = self.adapter.accept_webhook(url, params, signature)
        if inbound is None:
            return 403, []
        return 200, self.handle_inbound(inbound.sender, inbound.body)
