from __future__ import annotations

import asyncio
from pathlib import Path

from app.domain.task import TaskRequest, TaskStatus
from app.orchestration.agent_loop import AgentLoopResult
from app.orchestration.execution_lease import ExecutionLeaseManager
from app.orchestration.runners.base import AgentRunner, RunnerInput
from app.orchestration.task_orchestrator import TaskOrchestrator
from app.orchestration.task_scheduler import TaskScheduler
from app.storage.task_store import InMemoryTaskStore
from app.tools.models import ToolResult
from app.verification.models import VerificationContext
from app.verification.verifier import BasicVerificationService
from app.workspace.workspace_manager import WorkspaceManager


def test_verifier_keyword_tables_are_english_ascii() -> None:
    keywords = (
        BasicVerificationService.ARTIFACT_KEYWORDS
        | BasicVerificationService.COMMAND_KEYWORDS
    )

    assert keywords
    assert all(keyword.isascii() for keyword in keywords)


def test_verifier_accepts_finished_report_with_artifact(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "report.md").write_text("# Report\n", encoding="utf-8")
    loop_result = AgentLoopResult(
        status="finished",
        final_response="done",
        messages=[],
        tool_results=[
            ToolResult(
                tool_name="write_artifact",
                request_id="call_write",
                success=True,
                content="wrote report",
            ),
            ToolResult(
                tool_name="finish_task",
                request_id="call_finish",
                success=True,
                content="done",
                data={"finished": True},
            ),
        ],
    )

    async def run():
        return await BasicVerificationService().verify(
            VerificationContext(
                task_request=TaskRequest(prompt="Create a report."),
                workspace_root=tmp_path / "workspace",
                artifact_root=artifacts,
                artifact_paths=["report.md"],
                loop_result=loop_result,
            )
        )

    result = asyncio.run(run())

    assert result.passed
    assert result.model_dump()["passed"] is True


def test_verifier_rejects_report_without_artifact(tmp_path: Path) -> None:
    loop_result = AgentLoopResult(
        status="finished",
        final_response="done",
        messages=[],
        tool_results=[
            ToolResult(
                tool_name="finish_task",
                request_id="call_finish",
                success=True,
                content="done",
                data={"finished": True},
            )
        ],
    )

    async def run():
        return await BasicVerificationService().verify(
            VerificationContext(
                task_request=TaskRequest(prompt="Create a report."),
                workspace_root=tmp_path / "workspace",
                artifact_root=tmp_path / "artifacts",
                artifact_paths=[],
                loop_result=loop_result,
            )
        )

    result = asyncio.run(run())

    assert not result.passed
    assert "artifact" in result.error_summary.lower()


def test_verifier_rejects_test_task_without_successful_command(tmp_path: Path) -> None:
    loop_result = AgentLoopResult(
        status="finished",
        final_response="done",
        messages=[],
        tool_results=[
            ToolResult(
                tool_name="finish_task",
                request_id="call_finish",
                success=True,
                content="done",
                data={"finished": True},
            )
        ],
    )

    async def run():
        return await BasicVerificationService().verify(
            VerificationContext(
                task_request=TaskRequest(prompt="Run pytest and finish."),
                workspace_root=tmp_path / "workspace",
                artifact_root=tmp_path / "artifacts",
                artifact_paths=[],
                loop_result=loop_result,
            )
        )

    result = asyncio.run(run())

    assert not result.passed
    assert "controlled command" in result.error_summary


def test_verifier_accepts_successful_controlled_command(tmp_path: Path) -> None:
    loop_result = AgentLoopResult(
        status="finished",
        final_response="done",
        messages=[],
        tool_results=[
            ToolResult(
                tool_name="run_test",
                request_id="call_test",
                success=True,
                content="tests passed",
            ),
            ToolResult(
                tool_name="finish_task",
                request_id="call_finish",
                success=True,
                content="done",
                data={"finished": True},
            ),
        ],
    )

    async def run():
        return await BasicVerificationService().verify(
            VerificationContext(
                task_request=TaskRequest(prompt="Run pytest and finish."),
                workspace_root=tmp_path / "workspace",
                artifact_root=tmp_path / "artifacts",
                artifact_paths=[],
                loop_result=loop_result,
            )
        )

    result = asyncio.run(run())

    assert result.passed


def test_orchestrator_fails_completed_report_without_artifact(tmp_path: Path) -> None:
    async def run() -> None:
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = ExecutionLeaseManager(store)
        task = await scheduler.submit(
            TaskRequest(prompt="Create a report."),
            task_id="task-verify",
        )
        lease = await leases.acquire(task.id, "worker-a")
        orchestrator = TaskOrchestrator(
            task_store=store,
            runner=StaticRunner(
                AgentLoopResult(
                    status="completed",
                    final_response="done",
                    messages=[],
                )
            ),
            workspace_manager=WorkspaceManager(tmp_path),
        )

        result = await orchestrator.run(
            task.id,
            lease,
        )
        stored = await store.require(task.id)

        assert result.status == TaskStatus.FAILED
        assert stored.result is not None
        assert stored.result.metadata["verification"]["passed"] is False
        assert "artifact" in (stored.result.error or "").lower()

    asyncio.run(run())


class StaticRunner(AgentRunner):
    def __init__(self, result: AgentLoopResult) -> None:
        self.result = result

    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        return self.result
