from __future__ import annotations

import asyncio
import contextlib
from uuid import uuid4

from app.orchestration.errors import ExecutionLeaseError
from app.orchestration.execution_lease import ExecutionLeaseManager
from app.orchestration.models import WorkerResult
from app.orchestration.task_orchestrator import TaskOrchestrator
from app.orchestration.task_scheduler import TaskScheduler


class TaskWorker:
    def __init__(
        self,
        scheduler: TaskScheduler,
        lease_manager: ExecutionLeaseManager,
        orchestrator: TaskOrchestrator,
        *,
        worker_id: str | None = None,
        poll_interval_seconds: float = 1.0,
        lease_heartbeat_interval_seconds: float = 30.0,
    ) -> None:
        self.scheduler = scheduler
        self.lease_manager = lease_manager
        self.orchestrator = orchestrator
        self.worker_id = worker_id or f"worker-{uuid4().hex}"
        self.poll_interval_seconds = poll_interval_seconds
        self.lease_heartbeat_interval_seconds = lease_heartbeat_interval_seconds
        self._running = False

    async def process_once(self) -> WorkerResult:
        task = await self.scheduler.next_task()
        if task is None:
            return WorkerResult(
                worker_id=self.worker_id,
                task_id=None,
                processed=False,
            )

        lease = await self.lease_manager.acquire(task.id, self.worker_id)
        heartbeat_task = asyncio.create_task(self._heartbeat_lease(lease.id))
        try:
            result = await self.orchestrator.run(task.id, lease)
            return WorkerResult(
                worker_id=self.worker_id,
                task_id=task.id,
                processed=True,
                status=result.status,
                error=result.error,
            )
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
            await self.lease_manager.release(lease.id)

    async def run_until_idle(self, *, max_tasks: int | None = None) -> list[WorkerResult]:
        results: list[WorkerResult] = []
        while max_tasks is None or len(results) < max_tasks:
            result = await self.process_once()
            if not result.processed:
                break
            results.append(result)
        return results

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            result = await self.process_once()
            if not result.processed:
                await asyncio.sleep(self.poll_interval_seconds)

    def stop(self) -> None:
        self._running = False

    async def _heartbeat_lease(self, lease_id: str) -> None:
        while True:
            await asyncio.sleep(self.lease_heartbeat_interval_seconds)
            try:
                await self.lease_manager.heartbeat(lease_id)
            except ExecutionLeaseError:
                return
