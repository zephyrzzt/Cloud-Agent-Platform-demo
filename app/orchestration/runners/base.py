from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.orchestration.agent_loop import AgentLoopResult


@dataclass(frozen=True)
class RunnerInput:
    task: str
    task_id: str = "local-task"
    workspace_root: str | Path = "."
    artifact_root: str | Path | None = None
    allow_write: bool = False
    role: str = "agent"
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRunner(ABC):
    @abstractmethod
    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        raise NotImplementedError
