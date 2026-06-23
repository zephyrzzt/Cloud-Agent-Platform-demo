from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.bootstrap.container import create_container
from app.config.settings import Settings
from app.context.budget import ContextBudget
from app.context.compaction_policy import CompactionPolicy
from app.context.file_buffer import FileBuffer
from app.context.lane import ContextLane
from app.context.models import ContextRole
from app.context.recall import RecallService
from app.domain.task import TaskRequest, TaskStatus
from app.orchestration.agent_loop import AgentLoopResult
from app.orchestration.execution_modes import ExecutionMode, TaskPhase
from app.orchestration.execution_router import ExecutionRouter
from app.orchestration.failures.circuit_breaker import FailureCircuitBreaker
from app.orchestration.failures.detectors import FailureDetector
from app.orchestration.failures.ledger import FailureLedger
from app.orchestration.multi_agent.blackboard import Blackboard
from app.orchestration.multi_agent.roles import AgentRole
from app.orchestration.recovery_service import RecoveryService
from app.orchestration.reviewer_debug.service import ReviewerDebugService
from app.orchestration.reviewer_debug.trigger import ReviewerDebugTrigger
from app.orchestration.runners.base import AgentRunner, RunnerInput
from app.orchestration.runners.sequential import PhaseRunner, SequentialRunner
from app.orchestration.runners.sync_multi_agent import SyncMultiAgentRunner
from app.orchestration.task_classifier import TaskClassifier
from app.orchestration.execution_lease import ExecutionLeaseManager
from app.orchestration.task_scheduler import TaskScheduler
from app.sandbox.errors import SandboxStartError
from app.sandbox.models import SandboxSpec
from app.sandbox.providers.firecracker import FirecrackerSandboxService
from app.sandbox.providers.kubernetes import KubernetesSandboxService
from app.storage.task_store import InMemoryTaskStore


def test_classifier_and_execution_router_select_sequential_runner() -> None:
    classifier = TaskClassifier()
    profile = classifier.classify(TaskRequest(prompt="implement fix and tests"))
    single = StaticRunner("single")
    sequential = StaticRunner("sequential")
    router = ExecutionRouter(single_runner=single, sequential_runner=sequential)

    assert profile.mode == ExecutionMode.SEQUENTIAL
    assert router.route(profile) is sequential


def test_sequential_runner_runs_phases_in_order(tmp_path: Path) -> None:
    async def run() -> None:
        base = StaticRunner("phase-ok")
        runner = SequentialRunner(
            [
                PhaseRunner(TaskPhase.EXPLORE, base),
                PhaseRunner(TaskPhase.DEVELOP, base),
                PhaseRunner(TaskPhase.REVIEW, base),
            ]
        )
        result = await runner.run(RunnerInput(task="work", workspace_root=tmp_path))

        assert result.completed
        assert [item.role for item in base.inputs] == [
            "explore",
            "develop",
            "review",
        ]

    asyncio.run(run())


def test_blackboard_enforces_role_write_boundaries() -> None:
    board = Blackboard()
    item = board.write("finding:auth", {"risk": "high"}, AgentRole.EXPLORER)

    assert item.version == 1
    assert board.read("finding:auth") == {"risk": "high"}
    with pytest.raises(Exception):
        board.write("review:auth", "not allowed", AgentRole.EXPLORER)


def test_failure_ledger_circuit_breaker_and_reviewer_debug() -> None:
    detector = FailureDetector()
    ledger = FailureLedger()
    breaker = FailureCircuitBreaker(ledger, threshold=2)

    first = detector.from_text(task_id="t1", message="Assertion failed at line 10")
    second = detector.from_text(task_id="t1", message="Assertion failed at line 20")

    assert not breaker.record_and_check(first).open
    assert breaker.record_and_check(second).open

    service = ReviewerDebugService(ReviewerDebugTrigger(ledger, threshold=2))
    grant = service.maybe_grant("t1")

    assert grant is not None
    assert grant.is_active()


def test_context_compaction_file_buffer_and_recall(tmp_path: Path) -> None:
    lane = ContextLane(
        ContextRole.DEVELOPER,
        policy=CompactionPolicy(ContextBudget(max_tokens=20)),
    )
    for index in range(12):
        lane.append(f"important auth detail number {index} " * 3)

    snapshot = lane.snapshot()
    assert snapshot.estimated_tokens <= sum(entry.estimated_tokens for entry in snapshot.entries)
    assert any(entry.role == "summary" for entry in snapshot.entries)

    buffer = FileBuffer(tmp_path)
    buffered = buffer.write("auth token refresh details", description="auth notes")
    results = RecallService().search(
        "auth details",
        lanes=[lane],
        file_buffer=buffer,
    )

    assert buffered.path.is_file()
    assert results
    assert results[0].score > 0


def test_sync_multi_agent_runner_records_blackboard(tmp_path: Path) -> None:
    async def run() -> None:
        runners = {
            AgentRole.EXPLORER: StaticRunner("explored"),
            AgentRole.DEVELOPER: StaticRunner("developed"),
            AgentRole.REVIEWER: StaticRunner("reviewed"),
        }
        runner = SyncMultiAgentRunner(runners)
        result = await runner.run(RunnerInput(task="ship it", workspace_root=tmp_path))

        assert result.completed
        snapshot = runner.blackboard.snapshot()
        assert "finding:explore" in snapshot
        assert "implementation:develop" in snapshot
        assert "review:review" in snapshot

    asyncio.run(run())


def test_default_container_routes_sequential_tasks(tmp_path: Path) -> None:
    async def run() -> None:
        container = create_container(
            settings=Settings(
                default_model_provider="mock",
                default_model_name="mock-agent",
            ),
            workspace_root=tmp_path,
        )

        task = await container.scheduler.submit(
            TaskRequest(prompt="implement feature"),
            task_id="sequential-task",
        )
        result = await container.worker.process_once()
        stored = await container.task_store.require(task.id)

        assert result.status == TaskStatus.SUCCEEDED
        assert stored.result is not None
        assert stored.result.metadata["execution"]["mode"] == "sequential"
        assert stored.result.metadata["execution"]["phases"] == [
            "explore",
            "develop",
            "review",
        ]

    asyncio.run(run())


def test_default_container_routes_sync_tasks(tmp_path: Path) -> None:
    async def run() -> None:
        container = create_container(
            settings=Settings(
                default_model_provider="mock",
                default_model_name="mock-agent",
            ),
            workspace_root=tmp_path,
        )

        task = await container.scheduler.submit(
            TaskRequest(prompt="architecture system coordination"),
            task_id="sync-task",
        )
        result = await container.worker.process_once()
        stored = await container.task_store.require(task.id)

        assert result.status == TaskStatus.SUCCEEDED
        assert stored.result is not None
        assert stored.result.metadata["execution"]["mode"] == "sync"

    asyncio.run(run())


def test_recovery_service_requeues_stale_leased_task() -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = ExecutionLeaseManager(store)
        task = await scheduler.submit(TaskRequest(prompt="work"), task_id="t1")
        await leases.acquire(task.id, "worker-a")
        leased = await store.require(task.id)
        stale = leased.with_updates(
            updated_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        await store.update(stale)

        recovered = await RecoveryService(store).recover_stale_tasks(
            older_than_seconds=60
        )
        updated = await store.require(task.id)

        assert recovered == ["t1"]
        assert updated.status == TaskStatus.QUEUED

    asyncio.run(run())


def test_placeholder_sandbox_providers_are_explicit() -> None:
    async def run() -> None:
        spec = SandboxSpec(
            image="image",
            repository_path=".",
            artifacts_path=".",
        )
        for service in [KubernetesSandboxService(), FirecrackerSandboxService()]:
            with pytest.raises(SandboxStartError):
                await service.start_sandbox(spec)

    asyncio.run(run())


class StaticRunner(AgentRunner):
    def __init__(self, label: str) -> None:
        self.label = label
        self.inputs: list[RunnerInput] = []

    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        self.inputs.append(runner_input)
        return AgentLoopResult(
            status="completed",
            final_response=self.label,
            messages=[],
            turns=1,
            tool_calls=0,
        )
