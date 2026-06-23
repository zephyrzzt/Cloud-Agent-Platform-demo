from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class FailureKind(StrEnum):
    TOOL = "tool"
    TEST = "test"
    BUILD = "build"
    RUNTIME = "runtime"
    POLICY = "policy"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureRecord:
    task_id: str
    kind: FailureKind
    message: str
    fingerprint: str
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
