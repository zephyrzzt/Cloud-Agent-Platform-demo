from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.task import TaskStatus


@dataclass(frozen=True)
class OrchestratorResult:
    task_id: str
    status: TaskStatus
    summary: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerResult:
    worker_id: str
    task_id: str | None
    processed: bool
    status: TaskStatus | None = None
    error: str | None = None
