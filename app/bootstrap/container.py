from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.settings import Settings
from app.llm.config import ModelSelection
from app.llm.models import ModelResponse, ModelToolCall
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.registry import ModelRegistry
from app.llm.router import ModelRouter
from app.orchestration.agent_loop import AgentLoop, AgentLoopConfig, AgentLoopResult
from app.orchestration.execution_lease import ExecutionLeaseManager
from app.orchestration.execution_router import ExecutionRouter
from app.orchestration.multi_agent.roles import AgentRole
from app.orchestration.runners.base import AgentRunner, RunnerInput
from app.orchestration.runners.sequential import PhaseRunner, SequentialRunner
from app.orchestration.runners.single_agent import SingleAgentRunner
from app.orchestration.runners.sync_multi_agent import SyncMultiAgentRunner
from app.orchestration.execution_modes import TaskPhase
from app.orchestration.task_classifier import TaskClassifier
from app.orchestration.task_orchestrator import TaskOrchestrator
from app.orchestration.task_scheduler import TaskScheduler
from app.orchestration.task_state_machine import TaskStateMachine
from app.orchestration.task_worker import TaskWorker
from app.sandbox.providers.docker import DockerSandboxService
from app.sandbox.service import SandboxService
from app.tools.base import NativeTool
from app.storage.task_store import InMemoryTaskStore
from app.tools.executors.native_executor import NativeExecutor
from app.tools.native.command_tools import build_controlled_command_tools
from app.tools.registry import build_registry
from app.verification.verifier import BasicVerificationService, VerificationService
from app.workspace.repository_preparer import RepositoryPreparer
from app.workspace.workspace_manager import WorkspaceManager


@dataclass
class AppContainer:
    settings: Settings
    model_registry: ModelRegistry
    model_router: ModelRouter
    sandbox_services: dict[str, SandboxService]
    task_store: InMemoryTaskStore
    state_machine: TaskStateMachine
    scheduler: TaskScheduler
    lease_manager: ExecutionLeaseManager
    workspace_manager: WorkspaceManager
    repository_preparer: RepositoryPreparer
    verifier: VerificationService
    runner: AgentRunner
    sequential_runner: AgentRunner
    sync_runner: AgentRunner
    task_classifier: TaskClassifier
    execution_router: ExecutionRouter
    orchestrator: TaskOrchestrator
    worker: TaskWorker


class ConfigurableAgentRunner(AgentRunner):
    def __init__(
        self,
        *,
        settings: Settings,
        model_router: ModelRouter,
        sandbox_services: dict[str, SandboxService] | None = None,
        max_turns: int = 4,
        max_tool_calls: int = 8,
    ) -> None:
        self.settings = settings
        self.model_router = model_router
        self.sandbox_services = sandbox_services or {}
        self.max_turns = max_turns
        self.max_tool_calls = max_tool_calls

    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        registry = build_registry(
            include_write_tools=runner_input.allow_write,
            command_tools=self._sandbox_command_tools(runner_input),
        )
        executor = NativeExecutor(registry)
        provider = self._select_provider(runner_input)
        loop = AgentLoop(
            model_provider=provider,
            tool_registry=registry,
            tool_executor=executor,
            config=AgentLoopConfig(
                max_turns=self.max_turns,
                max_tool_calls=self.max_tool_calls,
            ),
        )
        return await SingleAgentRunner(loop).run(runner_input)

    def _select_provider(self, runner_input: RunnerInput):
        provider_name = runner_input.metadata.get(
            "model_provider",
            self.settings.default_model_provider,
        )
        model_name = runner_input.metadata.get(
            "model_name",
            self.settings.default_model_name,
        )
        if provider_name == "mock":
            return self._scripted_mock_provider(runner_input)
        return self.model_router.select(
            ModelSelection(provider=provider_name, model_name=model_name)
        )

    def _sandbox_command_tools(self, runner_input: RunnerInput) -> list[NativeTool]:
        sandbox_id = runner_input.metadata.get("sandbox_id")
        if not isinstance(sandbox_id, str) or not sandbox_id:
            return []

        provider_name = str(
            runner_input.metadata.get(
                "sandbox_provider",
                self.settings.sandbox_provider,
            )
        ).lower()
        if provider_name in {"", "disabled", "none"}:
            return []

        service = self.sandbox_services.get(provider_name)
        if service is None:
            return []

        return build_controlled_command_tools(
            sandbox_service=service,
            sandbox_id=sandbox_id,
            default_timeout_seconds=self.settings.sandbox_command_timeout_seconds,
            default_max_output_bytes=self.settings.sandbox_max_output_bytes,
        )

    def _scripted_mock_provider(self, runner_input: RunnerInput) -> MockProvider:
        return MockProvider.from_responses(
            [
                ModelResponse.tools(
                    [
                        ModelToolCall(
                            name="write_artifact",
                            arguments={
                                "path": "report.md",
                                "content": self._artifact_content(runner_input),
                            },
                        )
                    ]
                ),
                ModelResponse.tools(
                    [
                        ModelToolCall(
                            name="finish_task",
                            arguments={
                                "summary": (
                                    "Task completed by the MVP mock agent. "
                                    "Artifact written to report.md."
                                )
                            },
                        )
                    ]
                ),
            ]
        )

    def _artifact_content(self, runner_input: RunnerInput) -> str:
        return (
            "# MVP Task Report\n\n"
            f"Task ID: {runner_input.task_id}\n\n"
            "Prompt:\n\n"
            f"{runner_input.task}\n\n"
            "Status: completed by scripted MockProvider.\n"
        )


def create_container(
    *,
    settings: Settings | None = None,
    workspace_root: str | Path | None = None,
) -> AppContainer:
    settings = settings or Settings.from_env()
    resolved_workspace_root = workspace_root or settings.workspace_root
    task_store = InMemoryTaskStore()
    model_registry = create_model_registry(settings)
    model_router = ModelRouter(model_registry)
    sandbox_services = create_sandbox_services(settings)
    state_machine = TaskStateMachine()
    scheduler = TaskScheduler(
        task_store,
        state_machine,
        max_concurrent_tasks=settings.task_scheduler_max_concurrent_tasks,
        max_sandbox_tasks=settings.task_scheduler_max_sandbox_tasks,
    )
    lease_manager = ExecutionLeaseManager(
        task_store,
        state_machine,
        ttl_seconds=settings.task_worker_lease_ttl_seconds,
    )
    workspace_manager = WorkspaceManager(resolved_workspace_root)
    repository_preparer = RepositoryPreparer()
    verifier = BasicVerificationService()
    runner = ConfigurableAgentRunner(
        settings=settings,
        model_router=model_router,
        sandbox_services=sandbox_services,
        max_turns=settings.agent_max_turns,
        max_tool_calls=settings.agent_max_tool_calls,
    )
    sequential_runner = SequentialRunner(
        [
            PhaseRunner(TaskPhase.EXPLORE, runner),
            PhaseRunner(TaskPhase.DEVELOP, runner),
            PhaseRunner(TaskPhase.REVIEW, runner),
        ]
    )
    sync_runner = SyncMultiAgentRunner(
        {
            AgentRole.EXPLORER: runner,
            AgentRole.DEVELOPER: runner,
            AgentRole.REVIEWER: runner,
        }
    )
    task_classifier = TaskClassifier()
    execution_router = ExecutionRouter(
        single_runner=runner,
        sequential_runner=sequential_runner,
        sync_runner=sync_runner,
    )
    orchestrator = TaskOrchestrator(
        task_store=task_store,
        runner=runner,
        workspace_manager=workspace_manager,
        repository_preparer=repository_preparer,
        state_machine=state_machine,
        task_classifier=task_classifier,
        execution_router=execution_router,
        verifier=verifier,
        sandbox_services=sandbox_services,
        default_sandbox_provider=settings.sandbox_provider,
        default_sandbox_image=settings.sandbox_image,
        sandbox_network=settings.sandbox_network,
        sandbox_command_timeout_seconds=settings.sandbox_command_timeout_seconds,
        sandbox_max_output_bytes=settings.sandbox_max_output_bytes,
    )
    worker = TaskWorker(
        scheduler=scheduler,
        lease_manager=lease_manager,
        orchestrator=orchestrator,
        worker_id=settings.task_worker_id,
        poll_interval_seconds=settings.task_worker_poll_interval_seconds,
        lease_heartbeat_interval_seconds=(
            settings.task_worker_lease_heartbeat_interval_seconds
        ),
    )
    return AppContainer(
        settings=settings,
        model_registry=model_registry,
        model_router=model_router,
        sandbox_services=sandbox_services,
        task_store=task_store,
        state_machine=state_machine,
        scheduler=scheduler,
        lease_manager=lease_manager,
        workspace_manager=workspace_manager,
        repository_preparer=repository_preparer,
        verifier=verifier,
        runner=runner,
        sequential_runner=sequential_runner,
        sync_runner=sync_runner,
        task_classifier=task_classifier,
        execution_router=execution_router,
        orchestrator=orchestrator,
        worker=worker,
    )


def create_model_registry(settings: Settings) -> ModelRegistry:
    registry = ModelRegistry()
    registry.register(
        MockProvider(
            provider_name="mock",
            model_name=settings.default_model_name
            if settings.default_model_provider == "mock"
            else "mock-agent",
        )
    )
    registry.register(
        OpenAICompatibleProvider(
            model_name=settings.default_model_name,
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            timeout_seconds=settings.openai_compatible_timeout_seconds,
        )
    )
    return registry


def create_sandbox_services(settings: Settings) -> dict[str, SandboxService]:
    return {
        "docker": DockerSandboxService(),
    }
