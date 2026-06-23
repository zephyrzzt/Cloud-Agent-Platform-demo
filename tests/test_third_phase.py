from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from app.domain.task import RepositoryRef, TaskRequest, TaskStatus
from app.orchestration.agent_loop import AgentLoopResult
from app.orchestration.errors import (
    ExecutionLeaseNotAcquiredError,
    InvalidTaskTransitionError,
)
from app.orchestration.execution_lease import ExecutionLeaseManager
from app.orchestration.models import OrchestratorResult
from app.orchestration.runners.base import AgentRunner, RunnerInput
from app.orchestration.task_orchestrator import TaskOrchestrator
from app.orchestration.task_scheduler import TaskScheduler
from app.orchestration.task_state_machine import TaskStateMachine
from app.orchestration.task_worker import TaskWorker
from app.storage.task_store import InMemoryTaskStore
from app.workspace.workspace_manager import WorkspaceManager


def test_state_machine_rejects_invalid_transition() -> None:
    state_machine = TaskStateMachine()
    task = _make_task()

    with pytest.raises(InvalidTaskTransitionError):
        state_machine.transition(task, TaskStatus.SUCCEEDED)


def test_scheduler_submits_queued_task() -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)

        task = await scheduler.submit(TaskRequest(prompt="hello"), task_id="t1")
        next_task = await scheduler.next_task()

        assert task.status == TaskStatus.QUEUED
        assert next_task is not None
        assert next_task.id == "t1"

    asyncio.run(run())


def test_scheduler_prefers_higher_priority_tasks() -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)

        await scheduler.submit(
            TaskRequest(prompt="low", priority=1),
            task_id="low",
        )
        await scheduler.submit(
            TaskRequest(prompt="high", priority=10),
            task_id="high",
        )

        next_task = await scheduler.next_task()

        assert next_task is not None
        assert next_task.id == "high"

    asyncio.run(run())


def test_scheduler_blocks_when_max_concurrency_is_reached() -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store, max_concurrent_tasks=1)
        leases = ExecutionLeaseManager(store)

        active = await scheduler.submit(TaskRequest(prompt="active"), task_id="active")
        await scheduler.submit(TaskRequest(prompt="queued"), task_id="queued")
        await leases.acquire(active.id, "worker-a")

        assert await scheduler.next_task() is None

    asyncio.run(run())


def test_scheduler_skips_sandbox_task_when_sandbox_capacity_is_full() -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store, max_sandbox_tasks=1)
        leases = ExecutionLeaseManager(store)

        active = await scheduler.submit(
            TaskRequest(prompt="active", sandbox_provider="docker"),
            task_id="active-sandbox",
        )
        await leases.acquire(active.id, "worker-a")
        await scheduler.submit(
            TaskRequest(prompt="high sandbox", priority=10, sandbox_provider="docker"),
            task_id="queued-sandbox",
        )
        await scheduler.submit(
            TaskRequest(prompt="normal", priority=1),
            task_id="queued-normal",
        )

        next_task = await scheduler.next_task()

        assert next_task is not None
        assert next_task.id == "queued-normal"

    asyncio.run(run())


def test_execution_lease_marks_task_and_blocks_second_lease() -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        task = await scheduler.submit(TaskRequest(prompt="hello"), task_id="t1")
        leases = ExecutionLeaseManager(store, ttl_seconds=60)

        lease = await leases.acquire(task.id, "worker-a")
        leased_task = await store.require(task.id)

        assert leased_task.status == TaskStatus.LEASED
        assert leased_task.lease_id == lease.id

        with pytest.raises(ExecutionLeaseNotAcquiredError):
            await leases.acquire(task.id, "worker-b")

        await leases.release(lease.id)
        released = await leases.get(lease.id)
        assert released is not None
        assert released.is_released

    asyncio.run(run())


def test_worker_heartbeats_lease_during_long_task(tmp_path: Path) -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = CountingLeaseManager(store, ttl_seconds=1)
        worker = TaskWorker(
            scheduler=scheduler,
            lease_manager=leases,
            orchestrator=SlowOrchestrator(),
            worker_id="worker-a",
            lease_heartbeat_interval_seconds=0.01,
        )

        await scheduler.submit(TaskRequest(prompt="slow work"), task_id="slow")
        result = await worker.process_once()

        assert result.processed is True
        assert result.status == TaskStatus.SUCCEEDED
        assert leases.heartbeat_count >= 1

    asyncio.run(run())


def test_worker_runs_task_to_success(tmp_path: Path) -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = ExecutionLeaseManager(store)
        runner = StaticRunner("completed", "done")
        orchestrator = TaskOrchestrator(
            task_store=store,
            runner=runner,
            workspace_manager=WorkspaceManager(tmp_path),
        )
        worker = TaskWorker(
            scheduler=scheduler,
            lease_manager=leases,
            orchestrator=orchestrator,
            worker_id="worker-a",
        )

        task = await scheduler.submit(TaskRequest(prompt="do work"), task_id="t1")
        result = await worker.process_once()
        stored = await store.require(task.id)

        assert result.processed is True
        assert result.status == TaskStatus.SUCCEEDED
        assert stored.status == TaskStatus.SUCCEEDED
        assert stored.result is not None
        assert stored.result.summary == "done"
        assert stored.lease_id is None
        assert stored.scheduled_at is not None
        assert stored.preparing_at is not None
        assert stored.started_at is not None
        assert stored.verifying_at is not None
        assert stored.sandbox_started_at is None
        assert runner.inputs[0].task == "do work"

    asyncio.run(run())


def test_orchestrator_prepares_repository_for_runner(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")

    source = tmp_path / "source"
    source.mkdir()
    _git(["init"], cwd=source)
    (source / "README.md").write_text("hello from repo\n", encoding="utf-8")
    _git(["add", "README.md"], cwd=source)
    _git(
        [
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "initial",
        ],
        cwd=source,
    )
    commit = _git(["rev-parse", "HEAD"], cwd=source).stdout.strip()

    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = ExecutionLeaseManager(store)
        runner = StaticRunner("completed", "done")
        orchestrator = TaskOrchestrator(
            task_store=store,
            runner=runner,
            workspace_manager=WorkspaceManager(tmp_path / "workspaces"),
        )

        task = await scheduler.submit(
            TaskRequest(
                prompt="inspect repository",
                repository=RepositoryRef(url=str(source)),
            ),
            task_id="repo-task",
        )
        lease = await leases.acquire(task.id, "worker-a")
        result = await orchestrator.run(task.id, lease)
        stored = await store.require(task.id)

        assert result.status == TaskStatus.SUCCEEDED
        assert runner.inputs
        assert (Path(runner.inputs[0].workspace_root) / "README.md").read_text(
            encoding="utf-8"
        ) == "hello from repo\n"
        assert stored.result is not None
        repository_metadata = stored.result.metadata["repository"]
        assert repository_metadata["provided"] is True
        assert repository_metadata["resolved_commit"] == commit

    asyncio.run(run())


def test_worker_records_failed_runner_result(tmp_path: Path) -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = ExecutionLeaseManager(store)
        runner = StaticRunner("turn_limit_reached", "not done")
        orchestrator = TaskOrchestrator(
            task_store=store,
            runner=runner,
            workspace_manager=WorkspaceManager(tmp_path),
        )
        worker = TaskWorker(scheduler, leases, orchestrator, worker_id="worker-a")

        task = await scheduler.submit(TaskRequest(prompt="do work"), task_id="t1")
        result = await worker.process_once()
        stored = await store.require(task.id)

        assert result.processed is True
        assert result.status == TaskStatus.FAILED
        assert stored.status == TaskStatus.FAILED
        assert stored.result is not None
        assert stored.result.error == "turn_limit_reached"

    asyncio.run(run())


def test_worker_returns_idle_when_no_task(tmp_path: Path) -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = ExecutionLeaseManager(store)
        orchestrator = TaskOrchestrator(
            task_store=store,
            runner=StaticRunner("completed", "done"),
            workspace_manager=WorkspaceManager(tmp_path),
        )
        worker = TaskWorker(scheduler, leases, orchestrator, worker_id="worker-a")

        result = await worker.process_once()

        assert result.processed is False
        assert result.task_id is None

    asyncio.run(run())


def _make_task():
    from app.domain.task import Task

    return Task.create(TaskRequest(prompt="hello"), task_id="t1")


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


class StaticRunner(AgentRunner):
    def __init__(self, status: str, final_response: str) -> None:
        self.status = status
        self.final_response = final_response
        self.inputs: list[RunnerInput] = []

    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        self.inputs.append(runner_input)
        return AgentLoopResult(
            status=self.status,
            final_response=self.final_response,
            messages=[],
            turns=1,
            tool_calls=0,
        )


class CountingLeaseManager(ExecutionLeaseManager):
    def __init__(self, task_store: InMemoryTaskStore, *, ttl_seconds: int = 300) -> None:
        super().__init__(task_store, ttl_seconds=ttl_seconds)
        self.heartbeat_count = 0

    async def heartbeat(self, lease_id: str):
        self.heartbeat_count += 1
        return await super().heartbeat(lease_id)


class SlowOrchestrator:
    async def run(self, task_id, lease) -> OrchestratorResult:
        await asyncio.sleep(0.05)
        return OrchestratorResult(
            task_id=task_id,
            status=TaskStatus.SUCCEEDED,
            summary="slow task done",
        )
