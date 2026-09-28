"""JSON persistence for subscribers and per-recipient alert receipts.

The default path is gitignored. Do not commit a store that contains real numbers.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Subscriber:
    subscriber_id: str
    display_name: str
    address: str
    status: str = "invited"
    opted_out: bool = False


@dataclass
class Approval:
    name: str
    address: str


@dataclass
class StoreData:
    subscribers: list[Subscriber] = field(default_factory=list)
    approvals: list[Approval] = field(default_factory=list)
    owner_address: str = ""
    alert_receipts: dict[str, str] = field(default_factory=dict)
    owner_notified: list[str] = field(default_factory=list)
    unapproved_attempts: list[str] = field(default_factory=list)

    def approval_for_address(self, address: str) -> Approval | None:
        for approval in self.approvals:
            if approval.address == address:
                return approval
        return None

    def subscriber_by_address(self, address: str) -> Subscriber | None:
        for person in self.subscribers:
            if person.address == address:
                return person
        return None

    def active(self) -> list[Subscriber]:
        return [person for person in self.subscribers if person.status == "active" and not person.opted_out]


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = StoreData()
        if path.exists():
            self.load()

    def load(self) -> None:
        raw = json.loads(self.path.read_text())
        self.data = StoreData(
            subscribers=[Subscriber(**item) for item in raw.get("subscribers", [])],
            approvals=[Approval(**item) for item in raw.get("approvals", [])],
            owner_address=raw.get("owner_address", ""),
            alert_receipts=dict(raw.get("alert_receipts", {})),
            owner_notified=list(raw.get("owner_notified", [])),
            unapproved_attempts=list(raw.get("unapproved_attempts", [])),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "subscribers": [asdict(person) for person in self.data.subscribers],
            "approvals": [asdict(approval) for approval in self.data.approvals],
            "owner_address": self.data.owner_address,
            "alert_receipts": self.data.alert_receipts,
            "owner_notified": self.data.owner_notified,
            "unapproved_attempts": self.data.unapproved_attempts,
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n")

    def receipt_key(self, alert_id: str, address: str) -> str:
        return f"{alert_id}|{address}"

    def alert_received(self, alert_id: str, address: str, updated: str) -> bool:
        return self.data.alert_receipts.get(self.receipt_key(alert_id, address)) == updated

    def mark_alert(self, alert_id: str, address: str, updated: str) -> None:
        self.data.alert_receipts[self.receipt_key(alert_id, address)] = updated
        self.save()
