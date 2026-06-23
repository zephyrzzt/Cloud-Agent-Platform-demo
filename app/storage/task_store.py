from __future__ import annotations

import asyncio
from collections.abc import Iterable

from app.domain.task import Task, TaskStatus


class TaskStoreError(RuntimeError):
    pass


class TaskNotFoundError(TaskStoreError):
    pass


class DuplicateTaskError(TaskStoreError):
    pass


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def create(self, task: Task) -> Task:
        async with self._lock:
            if task.id in self._tasks:
                raise DuplicateTaskError(f"Task already exists: {task.id}")
            self._tasks[task.id] = task
            return task

    async def get(self, task_id: str) -> Task | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def require(self, task_id: str) -> Task:
        task = await self.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return task

    async def update(self, task: Task) -> Task:
        async with self._lock:
            if task.id not in self._tasks:
                raise TaskNotFoundError(f"Task not found: {task.id}")
            self._tasks[task.id] = task
            return task

    async def compare_and_update(
        self,
        task_id: str,
        expected_status: TaskStatus,
        updated: Task,
    ) -> bool:
        async with self._lock:
            current = self._tasks.get(task_id)
            if current is None:
                raise TaskNotFoundError(f"Task not found: {task_id}")
            if current.status != expected_status:
                return False
            self._tasks[task_id] = updated
            return True

    async def list(
        self,
        *,
        statuses: Iterable[TaskStatus] | None = None,
    ) -> list[Task]:
        async with self._lock:
            items = list(self._tasks.values())
        if statuses is None:
            return items
        allowed = set(statuses)
        return [task for task in items if task.status in allowed]

    async def find_next_queued(self) -> Task | None:
        queued = await self.list(statuses=[TaskStatus.QUEUED])
        queued.sort(key=lambda task: task.queued_at or task.created_at)
        return queued[0] if queued else None


TaskStore = InMemoryTaskStore
