from __future__ import annotations

from app.orchestration.execution_modes import ExecutionMode, TaskProfile
from app.orchestration.runners.base import AgentRunner


class ExecutionRouter:
    def __init__(
        self,
        *,
        single_runner: AgentRunner,
        sequential_runner: AgentRunner | None = None,
        sync_runner: AgentRunner | None = None,
    ) -> None:
        self.single_runner = single_runner
        self.sequential_runner = sequential_runner or single_runner
        self.sync_runner = sync_runner or self.sequential_runner

    def route(self, profile: TaskProfile) -> AgentRunner:
        if profile.mode == ExecutionMode.SINGLE:
            return self.single_runner
        if profile.mode == ExecutionMode.SEQUENTIAL:
            return self.sequential_runner
        if profile.mode == ExecutionMode.SYNC:
            return self.sync_runner
        return self.single_runner
