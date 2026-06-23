from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.task import TaskResult, TaskStatus
from app.orchestration.task_state_machine import TaskStateMachine
from app.storage.task_store import InMemoryTaskStore


class RecoveryService:
    def __init__(
        self,
        task_store: InMemoryTaskStore,
        state_machine: TaskStateMachine | None = None,
    ) -> None:
        self.task_store = task_store
        self.state_machine = state_machine or TaskStateMachine()

    async def recover_stale_tasks(
        self,
        *,
        older_than_seconds: int = 900,
    ) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
        recovered: list[str] = []
        candidates = await self.task_store.list(
            statuses=[
                TaskStatus.LEASED,
                TaskStatus.SCHEDULED,
                TaskStatus.PREPARING,
                TaskStatus.SANDBOX_STARTING,
                TaskStatus.RUNNING,
                TaskStatus.VERIFYING,
            ]
        )
        for task in candidates:
            if task.updated_at > cutoff:
                continue
            if task.status == TaskStatus.LEASED:
                updated = self.state_machine.transition(task, TaskStatus.QUEUED)
            else:
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    summary="Recovered stale running task as failed.",
                    error="stale_running_task",
                )
                updated = self.state_machine.transition(
                    task,
                    TaskStatus.FAILED,
                    result=result,
                    error=result.error,
                )
            await self.task_store.update(updated)
            recovered.append(task.id)
        return recovered
