from __future__ import annotations

from app.orchestration.execution_modes import TaskPhase, TaskProfile


class PhaseRouter:
    def phases_for(self, profile: TaskProfile) -> list[TaskPhase]:
        if profile.phases:
            return list(profile.phases)
        return [TaskPhase.EXPLORE]
