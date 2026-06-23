from __future__ import annotations

from app.context.compaction_policy import CompactionPolicy
from app.context.compactors import ContextCompactor
from app.context.models import ContextEntry, ContextRole, ContextSnapshot


class ContextLane:
    def __init__(
        self,
        role: ContextRole,
        *,
        policy: CompactionPolicy | None = None,
        compactor: ContextCompactor | None = None,
    ) -> None:
        self.role = role
        self.policy = policy or CompactionPolicy()
        self.compactor = compactor or ContextCompactor()
        self._entries: list[ContextEntry] = []

    def append(
        self,
        content: str,
        *,
        role: str = "note",
        metadata: dict | None = None,
    ) -> ContextEntry:
        entry = ContextEntry(content=content, role=role, metadata=metadata or {})
        self._entries.append(entry)
        self._entries = self.compactor.compact(
            self._entries,
            self.policy.level_for(self.estimated_tokens),
        )
        return entry

    @property
    def entries(self) -> list[ContextEntry]:
        return list(self._entries)

    @property
    def estimated_tokens(self) -> int:
        return sum(entry.estimated_tokens for entry in self._entries)

    def snapshot(self) -> ContextSnapshot:
        summary = "\n".join(entry.content for entry in self._entries if entry.role == "summary")
        return ContextSnapshot(
            lane=self.role,
            entries=self.entries,
            estimated_tokens=self.estimated_tokens,
            summary=summary,
        )
