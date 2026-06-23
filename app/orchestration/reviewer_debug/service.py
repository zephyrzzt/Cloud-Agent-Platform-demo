from __future__ import annotations

from dataclasses import replace

from app.orchestration.reviewer_debug.models import (
    ReviewerDebugGrant,
    ReviewerDebugStatus,
)
from app.orchestration.reviewer_debug.trigger import ReviewerDebugTrigger


class ReviewerDebugService:
    def __init__(self, trigger: ReviewerDebugTrigger) -> None:
        self.trigger = trigger
        self._grants: dict[str, ReviewerDebugGrant] = {}

    def maybe_grant(
        self,
        task_id: str,
        *,
        allowed_tools: set[str] | None = None,
    ) -> ReviewerDebugGrant | None:
        should_trigger, reason = self.trigger.should_trigger(task_id)
        if not should_trigger:
            return None

        grant = ReviewerDebugGrant(
            task_id=task_id,
            reason=reason,
            allowed_tools=allowed_tools or {"read_file", "search_code"},
        )
        self._grants[grant.id] = grant
        return grant

    def get(self, grant_id: str) -> ReviewerDebugGrant | None:
        grant = self._grants.get(grant_id)
        if grant is None:
            return None
        if not grant.is_active():
            expired = replace(grant, status=ReviewerDebugStatus.EXPIRED)
            self._grants[grant_id] = expired
            return expired
        return grant

    def mark_used(self, grant_id: str) -> ReviewerDebugGrant:
        grant = self._grants[grant_id]
        updated = replace(grant, status=ReviewerDebugStatus.USED)
        self._grants[grant_id] = updated
        return updated

    def revoke(self, grant_id: str) -> ReviewerDebugGrant:
        grant = self._grants[grant_id]
        updated = replace(grant, status=ReviewerDebugStatus.REVOKED)
        self._grants[grant_id] = updated
        return updated
