from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class TaskType(StrEnum):
    CODING = "coding"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    REPORT = "report"
    MIXED = "mixed"


class TaskStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    LEASED = "leased"
    SCHEDULED = "scheduled"
    PREPARING = "preparing"
    SANDBOX_STARTING = "sandbox_starting"
    RUNNING = "running"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_TASK_STATUSES = {
    TaskStatus.SUCCEEDED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


ACTIVE_TASK_STATUSES = {
    TaskStatus.LEASED,
    TaskStatus.SCHEDULED,
    TaskStatus.PREPARING,
    TaskStatus.SANDBOX_STARTING,
    TaskStatus.RUNNING,
    TaskStatus.VERIFYING,
}


@dataclass(frozen=True)
class RepositoryRef:
    url: str
    ref: str | None = None
    access_token: str | None = None


@dataclass(frozen=True)
class TaskLimits:
    max_runtime_seconds: int = 900
    max_turns: int = 8
    max_tool_calls: int = 24
    token_budget: int | None = None


@dataclass(frozen=True)
class TaskRequest:
    prompt: str
    repository: RepositoryRef | None = None
    task_type: TaskType = TaskType.MIXED
    priority: int = 0
    model_provider: str = "mock"
    model_name: str = "mock-agent"
    sandbox_provider: str = "disabled"
    sandbox_image: str = "cloud-agent-sandbox:latest"
    allow_write: bool = False
    limits: TaskLimits = field(default_factory=TaskLimits)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskResult:
    status: TaskStatus
    summary: str = ""
    artifact_paths: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Task:
    id: str
    request: TaskRequest
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    queued_at: datetime | None = None
    scheduled_at: datetime | None = None
    preparing_at: datetime | None = None
    sandbox_started_at: datetime | None = None
    started_at: datetime | None = None
    verifying_at: datetime | None = None
    completed_at: datetime | None = None
    lease_id: str | None = None
    workspace_root: Path | None = None
    result: TaskResult | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        request: TaskRequest,
        *,
        task_id: str | None = None,
    ) -> "Task":
        return cls(id=task_id or uuid4().hex, request=request)

    def with_updates(self, **changes: Any) -> "Task":
        changes.setdefault("updated_at", datetime.now(timezone.utc))
        return replace(self, **changes)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_TASK_STATUSES
