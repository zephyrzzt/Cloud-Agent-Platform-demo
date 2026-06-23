from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import uuid4


class ReviewerDebugStatus(StrEnum):
    GRANTED = "granted"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class ReviewerDebugGrant:
    task_id: str
    reason: str
    allowed_tools: set[str] = field(default_factory=set)
    status: ReviewerDebugStatus = ReviewerDebugStatus.GRANTED
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15)
    )

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return self.status == ReviewerDebugStatus.GRANTED and self.expires_at > now
