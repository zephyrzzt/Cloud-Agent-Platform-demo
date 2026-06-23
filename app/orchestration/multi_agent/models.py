from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.orchestration.execution_modes import TaskPhase
from app.orchestration.multi_agent.roles import AgentRole


@dataclass(frozen=True)
class BlackboardItem:
    key: str
    value: Any
    role: AgentRole
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class DelegationRequest:
    task_id: str
    phase: TaskPhase
    role: AgentRole
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True)
class DelegationResult:
    request_id: str
    role: AgentRole
    phase: TaskPhase
    success: bool
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)
