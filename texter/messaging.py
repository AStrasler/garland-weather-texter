"""Provider-independent messaging for the Garland weather texter.

This module never opens a network connection. A live provider must supply a
transport. Tests use RecordingTransport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}
OWNER_EVENTS = ("unapproved_join",)


@dataclass(frozen=True)
class Outbound:
    to: str
    body: str
    kind: str


@dataclass(frozen=True)
class Inbound:
    sender: str
    body: str
    provider_message_id: str


@dataclass
class SendResult:
    accepted: bool
    provider_message_id: str = ""
    error: str = ""
    detail: str = ""


class Transport(Protocol):
    def deliver(self, message: Outbound) -> SendResult: ...


@dataclass
class RecordingTransport:
    sent: list[Outbound] = field(default_factory=list)
    fail_for: set[str] = field(default_factory=set)

    def deliver(self, message: Outbound) -> SendResult:
        if message.to in self.fail_for:
            return SendResult(False, error="transport rejected")
        self.sent.append(message)
        return SendResult(True, provider_message_id=f"mock-{len(self.sent)}")


@dataclass
class Subscriber:
    subscriber_id: str
    display_name: str
    address: str
    status: str = "approved"
    opted_out: bool = False


@dataclass
class Directory:
    """In-memory subscriber book. Do not persist real addresses in git."""

    people: dict[str, Subscriber] = field(default_factory=dict)
    approved_names: set[str] = field(default_factory=set)
    approved_addresses: dict[str, str] = field(default_factory=dict)
    owner_id: str = "owner"
    pending_notice: set[str] = field(default_factory=set)
    owner_notified: set[str] = field(default_factory=set)

    def add(self, person: Subscriber) -> None:
        self.people[person.subscriber_id] = person

    def by_address(self, address: str) -> Subscriber | None:
        for person in self.people.values():
            if person.address == address:
                return person
        return None

    def active(self) -> list[Subscriber]:
        return [person for person in self.people.values() if person.status == "active" and not person.opted_out]


@dataclass
class AlertLedger:
    sent: dict[str, str] = field(default_factory=dict)

    def is_new(self, alert_id: str, updated: str) -> bool:
        previous = self.sent.get(alert_id)
        if previous is None:
            return True
        return updated > previous

    def mark(self, alert_id: str, updated: str) -> None:
        self.sent[alert_id] = updated


class Texter:
    def __init__(self, transport: Transport, directory: Directory, ledger: AlertLedger | None = None):
        self.transport = transport
        self.directory = directory
        self.ledger = ledger or AlertLedger()

    def send(self, message: Outbound) -> SendResult:
        return self.transport.deliver(message)

    def deliver_to_active(self, body: str, kind: str) -> list[SendResult]:
        results = []
        for person in self.directory.active():
            results.append(self.send(Outbound(person.address, body, kind)))
        return results

    def deliver_alert(self, alert_id: str, updated: str, body: str) -> list[SendResult]:
        if not self.ledger.is_new(alert_id, updated):
            return []
        results = self.deliver_to_active(body, "alert")
        if results and all(result.accepted for result in results):
            self.ledger.mark(alert_id, updated)
        return results

    def handle_inbound(self, message: Inbound, welcome: str) -> list[Outbound]:
        word = message.body.strip().lower()
        person = self.directory.by_address(message.sender)
        sent: list[Outbound] = []
        if word in STOP_WORDS and person is not None:
            person.opted_out = True
            person.status = "opted_out"
            reply = Outbound(message.sender, "You are opted out of Garland weather texts. Reply JOIN to ask again.", "opt_out")
            self.send(reply)
            sent.append(reply)
            return sent
        if person is not None and person.opted_out and word != "join":
            return sent
        expected = self.directory.approved_addresses.get(message.sender)
        name = expected if expected and message.body.strip().lower() == expected.lower() else None
        if name and (person is None or person.status != "active"):
            if person is None:
                person = Subscriber(
                    subscriber_id=f"sub-{name.lower()}",
                    display_name=name,
                    address=message.sender,
                    status="active",
                )
                self.directory.add(person)
            else:
                person.display_name = name
                person.status = "active"
                person.opted_out = False
            reply = Outbound(message.sender, welcome, "welcome")
            self.send(reply)
            sent.append(reply)
            return sent
        if name is None and word not in STOP_WORDS:
            key = message.sender
            if key not in self.directory.pending_notice:
                self.directory.pending_notice.add(key)
                self.directory.owner_notified.add(key)
                owner = self.directory.people.get(self.directory.owner_id)
                if owner is not None:
                    notice = Outbound(
                        owner.address,
                        "Someone who is not on the approved list texted the weather line. They were not added.",
                        "owner_notice",
                    )
                    self.send(notice)
                    sent.append(notice)
        return sent

    def run_schedule(self, event: str, forecast: str, now: datetime | None = None) -> list[SendResult]:
        if event in {"weekly", "midweek"}:
            return self.deliver_to_active(forecast, event)
        if event == "thursday_check":
            pending = self.directory.pending_notice - self.directory.owner_notified
            if not pending:
                return []
            owner = self.directory.people.get(self.directory.owner_id)
            if owner is None:
                return []
            result = self.send(
                Outbound(
                    owner.address,
                    "An unapproved person tried to join the Garland weather texts. They were not added.",
                    "owner_notice",
                )
            )
            if result.accepted:
                self.directory.owner_notified.update(pending)
            return [result]
        return []


def _match_name(body: str, approved: set[str]) -> str | None:
    cleaned = " ".join(body.strip().split())
    for name in approved:
        if cleaned.lower() == name.lower():
            return name
    return None


class TwilioAdapter:
    """Builds Twilio-shaped requests. Sends only through an injected transport."""

    def __init__(self, from_number: str, transport: Transport):
        self.from_number = from_number
        self.transport = transport

    def send_sms(self, to: str, body: str, kind: str = "forecast") -> SendResult:
        if not to.startswith("+") or not body:
            return SendResult(False, error="refusing incomplete test payload")
        return self.transport.deliver(Outbound(to, body, kind))

    @staticmethod
    def parse_webhook(payload: dict) -> Inbound:
        return Inbound(
            sender=str(payload.get("From") or ""),
            body=str(payload.get("Body") or ""),
            provider_message_id=str(payload.get("MessageSid") or ""),
        )
