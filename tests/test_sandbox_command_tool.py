from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.bootstrap.container import ConfigurableAgentRunner
from app.config.settings import Settings
from app.domain.task import TaskRequest, TaskStatus
from app.llm.models import ModelResponse, ModelToolCall
from app.llm.providers.mock import MockProvider
from app.llm.registry import ModelRegistry
from app.llm.router import ModelRouter
from app.orchestration.execution_lease import ExecutionLeaseManager
from app.orchestration.runners.base import RunnerInput
from app.orchestration.task_orchestrator import TaskOrchestrator
from app.orchestration.task_scheduler import TaskScheduler
from app.sandbox.errors import SandboxPolicyViolationError
from app.sandbox.healthcheck import SandboxHealthcheck
from app.sandbox.image_manager import SandboxImageManager
from app.sandbox.models import (
    CommandResult,
    CommandSpec,
    NetworkPolicy,
    SandboxInfo,
    SandboxPage,
    SandboxSpec,
    SandboxStatus,
)
from app.sandbox.policy import SandboxPolicy
from app.sandbox.service import SandboxService
from app.storage.task_store import InMemoryTaskStore
from app.tools.executors.native_executor import NativeExecutor
from app.tools.models import ToolContext, ToolRequest
from app.tools.native.command_tools import build_controlled_command_tools
from app.tools.registry import build_registry
from app.workspace.workspace_manager import WorkspaceManager


def test_run_test_tool_uses_existing_task_sandbox(tmp_path: Path) -> None:
    service = FakeSandboxService(stdout="ok")
    registry = build_registry(
        command_tools=build_controlled_command_tools(
            sandbox_service=service,
            sandbox_id="sandbox-1",
        )
    )
    executor = NativeExecutor(registry)
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()

    async def run():
        return await executor.execute(
            ToolRequest(
                tool_name="run_test",
                arguments={"tool": "pytest", "path": ".", "args": ["-q"]},
            ),
            ToolContext(
                task_id="task-1",
                workspace_root=workspace,
                artifact_root=artifacts,
            ),
        )

    result = asyncio.run(run())

    assert result.success
    assert "stdout:\nok" == result.content
    assert {
        "run_test",
        "run_lint",
        "run_build",
        "run_compile",
        "run_program",
    }.issubset({tool.definition.name for tool in registry.list_tools()})
    assert not registry.has_tool("run_command")
    assert service.started_specs == []
    assert service.commands[0].argv == ["python", "-m", "pytest", ".", "-q"]
    assert service.command_sandbox_ids == ["sandbox-1"]
    assert service.deleted == []


def test_runner_exposes_controlled_command_tools_when_sandbox_is_selected(tmp_path: Path) -> None:
    service = FakeSandboxService(stdout="tests passed")
    provider = MockProvider(
        provider_name="scripted",
        model_name="scripted-model",
        responses=[
            ModelResponse.tools(
                [
                    ModelToolCall(
                        name="run_test",
                        arguments={"tool": "pytest", "path": ".", "args": ["-q"]},
                    )
                ]
            ),
            ModelResponse.tools(
                [
                    ModelToolCall(
                        name="finish_task",
                        arguments={"summary": "sandbox command completed"},
                    )
                ]
            ),
        ],
    )
    registry = ModelRegistry()
    registry.register(provider)
    runner = ConfigurableAgentRunner(
        settings=Settings(
            default_model_provider="scripted",
            default_model_name="scripted-model",
            sandbox_provider="docker",
            sandbox_image="cloud-agent-sandbox:test",
        ),
        model_router=ModelRouter(registry),
        sandbox_services={"docker": service},
    )

    async def run():
        return await runner.run(
            RunnerInput(
                task="Run the tests.",
                workspace_root=tmp_path / "workspace",
                artifact_root=tmp_path / "artifacts",
                metadata={
                    "model_provider": "scripted",
                    "model_name": "scripted-model",
                    "sandbox_provider": "docker",
                    "sandbox_id": "sandbox-1",
                },
            )
        )

    (tmp_path / "workspace").mkdir()
    result = asyncio.run(run())

    assert result.status == "finished"
    assert [item.tool_name for item in result.tool_results] == [
        "run_test",
        "finish_task",
    ]
    assert service.commands[0].argv == ["python", "-m", "pytest", ".", "-q"]
    assert service.started_specs == []
    assert service.deleted == []


def test_orchestrator_manages_task_sandbox_lifecycle(tmp_path: Path) -> None:
    service = FakeSandboxService(stdout="tests passed")
    provider = MockProvider(
        provider_name="scripted",
        model_name="scripted-model",
        responses=[
            ModelResponse.tools(
                [
                    ModelToolCall(
                        name="run_test",
                        arguments={"tool": "pytest", "path": ".", "args": ["-q"]},
                    )
                ]
            ),
            ModelResponse.tools(
                [
                    ModelToolCall(
                        name="finish_task",
                        arguments={"summary": "sandbox task completed"},
                    )
                ]
            ),
        ],
    )
    registry = ModelRegistry()
    registry.register(provider)
    runner = ConfigurableAgentRunner(
        settings=Settings(
            default_model_provider="scripted",
            default_model_name="scripted-model",
            sandbox_provider="docker",
            sandbox_image="cloud-agent-sandbox:test",
        ),
        model_router=ModelRouter(registry),
        sandbox_services={"docker": service},
    )

    async def run():
        store = InMemoryTaskStore()
        scheduler = TaskScheduler(store)
        leases = ExecutionLeaseManager(store)
        orchestrator = TaskOrchestrator(
            task_store=store,
            runner=runner,
            workspace_manager=WorkspaceManager(tmp_path),
            sandbox_services={"docker": service},
            sandbox_healthcheck=SandboxHealthcheck(required_tools=[]),
            default_sandbox_provider="docker",
            default_sandbox_image="cloud-agent-sandbox:test",
        )
        task = await scheduler.submit(
            TaskRequest(
                prompt="Run the tests.",
                model_provider="scripted",
                model_name="scripted-model",
                sandbox_provider="docker",
                sandbox_image="cloud-agent-sandbox:test",
                metadata={"requires_command": True},
            ),
            task_id="sandbox-task",
        )
        lease = await leases.acquire(task.id, "worker-a")
        result = await orchestrator.run(task.id, lease)
        stored = await store.require(task.id)
        return result, stored

    result, stored = asyncio.run(run())

    assert result.status == TaskStatus.SUCCEEDED
    assert stored.result is not None
    assert stored.sandbox_started_at is not None
    assert len(service.started_specs) == 1
    assert service.started_specs[0].image == "cloud-agent-sandbox:test"
    assert service.started_specs[0].network_policy == NetworkPolicy.DISABLED
    assert service.deleted == ["sandbox-1"]
    assert service.commands[-1].argv == ["python", "-m", "pytest", ".", "-q"]
    assert set(service.command_sandbox_ids) == {"sandbox-1"}
    sandbox_metadata = stored.result.metadata["sandbox"]
    assert sandbox_metadata["enabled"] is True
    assert sandbox_metadata["healthcheck"]["ok"] is True
    assert sandbox_metadata["cleanup"] == {"deleted": True}


def test_sandbox_policy_rejects_workdir_escape(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    artifacts = tmp_path / "artifacts"
    repository.mkdir()
    artifacts.mkdir()
    spec = SandboxSpec(
        image="cloud-agent-sandbox:test",
        repository_path=repository,
        artifacts_path=artifacts,
    ).normalized()

    with pytest.raises(SandboxPolicyViolationError):
        SandboxPolicy().validate_command(
            CommandSpec.shell("pwd", working_directory="/etc"),
            spec,
        )


def test_sandbox_image_manager_builds_expected_command() -> None:
    command = SandboxImageManager(docker_binary="docker").build_command(
        image="cloud-agent-sandbox:test",
        dockerfile="sandbox/Dockerfile",
        context="sandbox",
    )

    assert command == [
        "docker",
        "build",
        "-t",
        "cloud-agent-sandbox:test",
        "-f",
        "sandbox/Dockerfile",
        "sandbox",
    ]


class FakeSandboxService(SandboxService):
    def __init__(self, *, stdout: str = "", stderr: str = "", exit_code: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.started_specs: list[SandboxSpec] = []
        self.commands: list[CommandSpec] = []
        self.command_sandbox_ids: list[str] = []
        self.deleted: list[str] = []

    async def search_sandboxes(
        self,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxPage:
        return SandboxPage(items=[])

    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo | None:
        return SandboxInfo(
            id=sandbox_id,
            status=SandboxStatus.RUNNING,
            image="fake",
        )

    async def start_sandbox(
        self,
        spec: SandboxSpec,
        sandbox_id: str | None = None,
    ) -> SandboxInfo:
        self.started_specs.append(spec)
        return SandboxInfo(
            id=sandbox_id or "sandbox-1",
            status=SandboxStatus.RUNNING,
            image=spec.image,
        )

    async def execute(
        self,
        sandbox_id: str,
        command: CommandSpec | list[str] | str,
        workdir: str = "/workspace/repository",
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        command_spec = command if isinstance(command, CommandSpec) else CommandSpec.shell(str(command))
        self.command_sandbox_ids.append(sandbox_id)
        self.commands.append(command_spec)
        return CommandResult(
            sandbox_id=sandbox_id,
            command=command_spec.argv,
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
        )

    async def pause_sandbox(self, sandbox_id: str) -> bool:
        return True

    async def resume_sandbox(self, sandbox_id: str) -> bool:
        return True

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        self.deleted.append(sandbox_id)
        return True
