from __future__ import annotations

from app.domain.task import ACTIVE_TASK_STATUSES, Task, TaskRequest, TaskStatus
from app.orchestration.task_state_machine import TaskStateMachine
from app.storage.task_store import InMemoryTaskStore


class TaskScheduler:
    def __init__(
        self,
        task_store: InMemoryTaskStore,
        state_machine: TaskStateMachine | None = None,
        *,
        max_concurrent_tasks: int | None = None,
        max_sandbox_tasks: int | None = None,
    ) -> None:
        self.task_store = task_store
        self.state_machine = state_machine or TaskStateMachine()
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_sandbox_tasks = max_sandbox_tasks

    async def submit(
        self,
        request: TaskRequest,
        *,
        task_id: str | None = None,
    ) -> Task:
        task = Task.create(request, task_id=task_id)
        task = self.state_machine.transition(task, TaskStatus.QUEUED)
        return await self.task_store.create(task)

    async def enqueue_existing(self, task_id: str) -> Task:
        task = await self.task_store.require(task_id)
        updated = self.state_machine.transition(task, TaskStatus.QUEUED)
        return await self.task_store.update(updated)

    async def next_task(self) -> Task | None:
        if await self._concurrency_full():
            return None

        queued = await self.task_store.list(statuses=[TaskStatus.QUEUED])
        queued.sort(
            key=lambda task: (
                -task.request.priority,
                task.queued_at or task.created_at,
                task.created_at,
            )
        )
        for task in queued:
            if await self._sandbox_capacity_available(task):
                return task
        return None

    async def _concurrency_full(self) -> bool:
        if self.max_concurrent_tasks is None:
            return False
        active = await self.task_store.list(statuses=ACTIVE_TASK_STATUSES)
        return len(active) >= self.max_concurrent_tasks

    async def _sandbox_capacity_available(self, task: Task) -> bool:
        if self.max_sandbox_tasks is None or not self._requires_sandbox(task):
            return True
        active = await self.task_store.list(statuses=ACTIVE_TASK_STATUSES)
        active_sandbox_tasks = [item for item in active if self._requires_sandbox(item)]
        return len(active_sandbox_tasks) < self.max_sandbox_tasks

    def _requires_sandbox(self, task: Task) -> bool:
        provider = task.request.sandbox_provider.strip().lower()
        return provider not in {"", "disabled", "none"}
