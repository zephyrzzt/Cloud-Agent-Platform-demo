from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.task import TaskStatus
from app.orchestration.errors import (
    ExecutionLeaseError,
    ExecutionLeaseNotAcquiredError,
)
from app.orchestration.task_state_machine import TaskStateMachine
from app.storage.task_store import InMemoryTaskStore


@dataclass(frozen=True)
class ExecutionLease:
    id: str
    task_id: str
    worker_id: str
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None = None

    @property
    def is_released(self) -> bool:
        return self.released_at is not None

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return self.expires_at <= now


class ExecutionLeaseManager:
    def __init__(
        self,
        task_store: InMemoryTaskStore,
        state_machine: TaskStateMachine | None = None,
        ttl_seconds: int = 300,
    ) -> None:
        self.task_store = task_store
        self.state_machine = state_machine or TaskStateMachine()
        self.ttl_seconds = ttl_seconds
        self._leases: dict[str, ExecutionLease] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        task_id: str,
        worker_id: str,
    ) -> ExecutionLease:
        async with self._lock:
            task = await self.task_store.require(task_id)
            if task.status != TaskStatus.QUEUED:
                raise ExecutionLeaseNotAcquiredError(
                    f"Task is not queued: {task_id}"
                )

            active = self._active_lease_for_task(task_id)
            if active is not None:
                raise ExecutionLeaseNotAcquiredError(
                    f"Task already has an active lease: {task_id}"
                )

            now = datetime.now(timezone.utc)
            lease = ExecutionLease(
                id=uuid4().hex,
                task_id=task_id,
                worker_id=worker_id,
                acquired_at=now,
                expires_at=now + timedelta(seconds=self.ttl_seconds),
            )
            updated = self.state_machine.transition(
                task,
                TaskStatus.LEASED,
                lease_id=lease.id,
            )
            await self.task_store.update(updated)
            self._leases[lease.id] = lease
            return lease

    async def heartbeat(self, lease_id: str) -> ExecutionLease:
        async with self._lock:
            lease = self._require_active_lease(lease_id)
            updated = replace(
                lease,
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=self.ttl_seconds),
            )
            self._leases[lease_id] = updated
            return updated

    async def release(self, lease_id: str) -> None:
        async with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None or lease.is_released:
                return
            self._leases[lease_id] = replace(
                lease,
                released_at=datetime.now(timezone.utc),
            )

    async def get(self, lease_id: str) -> ExecutionLease | None:
        async with self._lock:
            return self._leases.get(lease_id)

    def _active_lease_for_task(self, task_id: str) -> ExecutionLease | None:
        now = datetime.now(timezone.utc)
        for lease in self._leases.values():
            if (
                lease.task_id == task_id
                and not lease.is_released
                and not lease.is_expired(now)
            ):
                return lease
        return None

    def _require_active_lease(self, lease_id: str) -> ExecutionLease:
        lease = self._leases.get(lease_id)
        if lease is None:
            raise ExecutionLeaseError(f"Lease not found: {lease_id}")
        if lease.is_released:
            raise ExecutionLeaseError(f"Lease is already released: {lease_id}")
        if lease.is_expired():
            raise ExecutionLeaseError(f"Lease is expired: {lease_id}")
        return lease
