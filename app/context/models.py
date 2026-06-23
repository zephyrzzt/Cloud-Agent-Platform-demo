from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ContextRole(StrEnum):
    GLOBAL = "global"
    MANAGER = "manager"
    EXPLORER = "explorer"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"


class CompactionLevel(StrEnum):
    NORMAL = "normal"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


@dataclass(frozen=True)
class ContextEntry:
    content: str
    role: str = "note"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def estimated_tokens(self) -> int:
        return max(1, len(self.content) // 4)


@dataclass(frozen=True)
class ContextSnapshot:
    lane: ContextRole
    entries: list[ContextEntry]
    estimated_tokens: int
    summary: str = ""
