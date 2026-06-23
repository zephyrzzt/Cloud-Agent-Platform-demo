from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.task import RepositoryRef, TaskRequest, TaskResult, TaskStatus
from app.orchestration.execution_lease import ExecutionLease
from app.orchestration.execution_modes import TaskProfile
from app.orchestration.execution_router import ExecutionRouter
from app.orchestration.models import OrchestratorResult
from app.orchestration.runners.base import AgentRunner, RunnerInput
from app.orchestration.task_classifier import TaskClassifier
from app.orchestration.task_state_machine import TaskStateMachine
from app.sandbox.errors import SandboxError
from app.sandbox.healthcheck import HealthcheckResult, SandboxHealthcheck
from app.sandbox.models import NetworkPolicy, SandboxInfo, SandboxSpec
from app.sandbox.service import SandboxService
from app.storage.task_store import InMemoryTaskStore
from app.verification.models import VerificationContext
from app.verification.verifier import BasicVerificationService, VerificationService
from app.workspace.repository_preparer import (
    PreparedRepository,
    RepositoryPreparer,
    RepositorySpec,
)
from app.workspace.workspace_manager import WorkspaceManager


@dataclass
class TaskSandboxRuntime:
    provider: str
    service: SandboxService
    spec: SandboxSpec
    info: SandboxInfo
    healthcheck: HealthcheckResult


class TaskOrchestrator:
    def __init__(
        self,
        task_store: InMemoryTaskStore,
        runner: AgentRunner,
        workspace_manager: WorkspaceManager,
        repository_preparer: RepositoryPreparer | None = None,
        state_machine: TaskStateMachine | None = None,
        task_classifier: TaskClassifier | None = None,
        execution_router: ExecutionRouter | None = None,
        verifier: VerificationService | None = None,
        sandbox_services: dict[str, SandboxService] | None = None,
        sandbox_healthcheck: SandboxHealthcheck | None = None,
        default_sandbox_provider: str = "disabled",
        default_sandbox_image: str = "cloud-agent-sandbox:latest",
        sandbox_network: str = "none",
        sandbox_command_timeout_seconds: int = 30,
        sandbox_max_output_bytes: int = 20_000,
        sandbox_healthcheck_timeout_seconds: int = 30,
    ) -> None:
        self.task_store = task_store
        self.runner = runner
        self.workspace_manager = workspace_manager
        self.repository_preparer = repository_preparer or RepositoryPreparer()
        self.state_machine = state_machine or TaskStateMachine()
        self.task_classifier = task_classifier
        self.execution_router = execution_router
        self.verifier = verifier or BasicVerificationService()
        self.sandbox_services = sandbox_services or {}
        self.sandbox_healthcheck = sandbox_healthcheck or SandboxHealthcheck()
        self.default_sandbox_provider = default_sandbox_provider
        self.default_sandbox_image = default_sandbox_image
        self.sandbox_network = sandbox_network
        self.sandbox_command_timeout_seconds = sandbox_command_timeout_seconds
        self.sandbox_max_output_bytes = sandbox_max_output_bytes
        self.sandbox_healthcheck_timeout_seconds = sandbox_healthcheck_timeout_seconds

    async def run(
        self,
        task_id: str,
        lease: ExecutionLease,
    ) -> OrchestratorResult:
        task = await self.task_store.require(task_id)
        task = self.state_machine.transition(
            task,
            TaskStatus.SCHEDULED,
            lease_id=lease.id,
        )
        await self.task_store.update(task)

        task = self.state_machine.transition(
            task,
            TaskStatus.PREPARING,
            lease_id=lease.id,
        )
        await self.task_store.update(task)

        layout = self.workspace_manager.create_workspace(task.id)
        prepared_repository: PreparedRepository | None = None
        task_sandbox: TaskSandboxRuntime | None = None
        completed_sandbox: TaskSandboxRuntime | None = None
        sandbox_cleanup: dict[str, Any] | None = None
        task_profile: TaskProfile | None = None
        try:
            if task.request.repository is not None:
                prepared_repository = self._prepare_repository(
                    task.request.repository,
                    layout.repository,
                )

            task = task.with_updates(workspace_root=layout.root)
            await self.task_store.update(task)

            workspace_root = (
                layout.repository if layout.repository.exists() else layout.root
            )
            if self._sandbox_requested(task.request):
                task = self.state_machine.transition(
                    await self.task_store.require(task.id),
                    TaskStatus.SANDBOX_STARTING,
                    lease_id=lease.id,
                )
                await self.task_store.update(task)

            task_sandbox = await self._start_task_sandbox_if_requested(
                task.request,
                workspace_root,
                layout.artifacts,
            )

            task = self.state_machine.transition(
                await self.task_store.require(task.id),
                TaskStatus.RUNNING,
                lease_id=lease.id,
            )
            await self.task_store.update(task)

            task_profile = self._classify_task(task.request)
            runner = self._select_runner(task_profile)
            loop_result = await runner.run(
                RunnerInput(
                    task=task.request.prompt,
                    task_id=task.id,
                    workspace_root=workspace_root,
                    artifact_root=layout.artifacts,
                    allow_write=task.request.allow_write,
                    role="agent",
                    metadata=self._runner_metadata(
                        task.request,
                        task_sandbox,
                        task_profile,
                    ),
                )
            )

            task = self.state_machine.transition(
                await self.task_store.require(task.id),
                TaskStatus.VERIFYING,
                lease_id=lease.id,
            )
            await self.task_store.update(task)

            artifact_paths = self._list_artifacts(layout.artifacts)
            verification = await self.verifier.verify(
                VerificationContext(
                    task_request=task.request,
                    workspace_root=workspace_root,
                    artifact_root=layout.artifacts,
                    artifact_paths=artifact_paths,
                    loop_result=loop_result,
                )
            )
            completed_sandbox = task_sandbox
            sandbox_cleanup = await self._cleanup_task_sandbox(task_sandbox)
            task_sandbox = None

            if loop_result.completed and verification.passed:
                result = TaskResult(
                    status=TaskStatus.SUCCEEDED,
                    summary=loop_result.final_response,
                    artifact_paths=artifact_paths,
                    metadata={
                        "agent_status": loop_result.status,
                        "turns": loop_result.turns,
                        "tool_calls": loop_result.tool_calls,
                        "workspace": self._workspace_metadata(layout),
                        "repository": self._repository_metadata(
                            prepared_repository,
                            layout.repository,
                        ),
                        "execution": self._execution_metadata(task_profile),
                        "sandbox": self._sandbox_metadata(
                            completed_sandbox,
                            sandbox_cleanup,
                        ),
                        "verification": verification.model_dump(),
                    },
                )
                updated = self.state_machine.transition(
                    await self.task_store.require(task.id),
                    TaskStatus.SUCCEEDED,
                    result=result,
                )
            else:
                error = (
                    verification.error_summary
                    if loop_result.completed
                    else loop_result.status
                )
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    summary=loop_result.final_response,
                    artifact_paths=artifact_paths,
                    error=error,
                    metadata={
                        "agent_status": loop_result.status,
                        "turns": loop_result.turns,
                        "tool_calls": loop_result.tool_calls,
                        "workspace": self._workspace_metadata(layout),
                        "repository": self._repository_metadata(
                            prepared_repository,
                            layout.repository,
                        ),
                        "execution": self._execution_metadata(task_profile),
                        "sandbox": self._sandbox_metadata(
                            completed_sandbox,
                            sandbox_cleanup,
                        ),
                        "verification": verification.model_dump(),
                    },
                )
                updated = self.state_machine.transition(
                    await self.task_store.require(task.id),
                    TaskStatus.FAILED,
                    result=result,
                    error=error,
                )

            await self.task_store.update(updated)
            return OrchestratorResult(
                task_id=task.id,
                status=updated.status,
                summary=result.summary,
                error=result.error,
                metadata=result.metadata,
            )
        except Exception as exc:
            completed_sandbox = task_sandbox
            sandbox_cleanup = await self._cleanup_task_sandbox(task_sandbox)
            task_sandbox = None
            result = TaskResult(
                status=TaskStatus.FAILED,
                summary="Task execution failed.",
                error=f"{type(exc).__name__}: {exc}",
                metadata={
                    "execution": self._execution_metadata(task_profile),
                    "sandbox": self._sandbox_metadata(
                        completed_sandbox,
                        sandbox_cleanup,
                    )
                },
            )
            current = await self.task_store.require(task.id)
            if not current.is_terminal:
                failed = self.state_machine.transition(
                    current,
                    TaskStatus.FAILED,
                    result=result,
                    error=result.error,
                )
                await self.task_store.update(failed)
            return OrchestratorResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                summary=result.summary,
                error=result.error,
                metadata=result.metadata,
            )

    def _prepare_repository(
        self,
        repository: RepositoryRef,
        destination: Path,
    ) -> PreparedRepository:
        return self.repository_preparer.prepare(
            RepositorySpec(
                url=repository.url,
                ref=repository.ref,
                access_token=repository.access_token,
            ),
            destination,
        )

    async def _start_task_sandbox_if_requested(
        self,
        request: TaskRequest,
        workspace_root: Path,
        artifact_root: Path,
    ) -> TaskSandboxRuntime | None:
        provider_name = self._sandbox_provider_name(request)
        if provider_name in {"", "disabled", "none"}:
            return None

        service = self.sandbox_services.get(provider_name)
        if service is None:
            raise SandboxError(f"Sandbox provider is not available: {provider_name}")

        artifact_root.mkdir(parents=True, exist_ok=True)
        spec = SandboxSpec(
            image=self._sandbox_image(request),
            repository_path=workspace_root,
            artifacts_path=artifact_root,
            network_policy=self._sandbox_network_policy(request),
            command_timeout_seconds=self.sandbox_command_timeout_seconds,
            max_output_bytes=self.sandbox_max_output_bytes,
        )

        sandbox = await service.start_sandbox(spec)
        try:
            ready = await service.wait_until_ready(
                sandbox.id,
                timeout=self.sandbox_healthcheck_timeout_seconds,
            )
            healthcheck = await self.sandbox_healthcheck.run(service, ready.id)
            if not healthcheck.ok:
                failed_checks = [
                    name for name, passed in healthcheck.checks.items() if not passed
                ]
                raise SandboxError(
                    "Sandbox healthcheck failed: " + ", ".join(failed_checks)
                )
            return TaskSandboxRuntime(
                provider=provider_name,
                service=service,
                spec=spec,
                info=ready,
                healthcheck=healthcheck,
            )
        except Exception:
            try:
                await service.delete_sandbox(sandbox.id)
            except SandboxError:
                pass
            raise

    async def _cleanup_task_sandbox(
        self,
        runtime: TaskSandboxRuntime | None,
    ) -> dict[str, Any] | None:
        if runtime is None:
            return None
        try:
            deleted = await runtime.service.delete_sandbox(runtime.info.id)
            return {"deleted": deleted}
        except SandboxError as exc:
            return {"deleted": False, "error": str(exc)}

    def _runner_metadata(
        self,
        request: TaskRequest,
        sandbox: TaskSandboxRuntime | None,
        profile: TaskProfile | None,
    ) -> dict[str, Any]:
        metadata = {
            **request.metadata,
            "task_type": request.task_type,
            "model_provider": request.model_provider,
            "model_name": request.model_name,
            "sandbox_provider": self._sandbox_provider_name(request),
            "sandbox_image": self._sandbox_image(request),
        }
        if profile is not None:
            metadata.update(
                {
                    "execution_mode": profile.mode.value,
                    "task_complexity": profile.complexity.value,
                    "task_phases": [phase.value for phase in profile.phases],
                }
            )
        if sandbox is not None:
            metadata.update(
                {
                    "sandbox_id": sandbox.info.id,
                    "sandbox_lifecycle": "task",
                }
            )
        return metadata

    def _sandbox_requested(self, request: TaskRequest) -> bool:
        return self._sandbox_provider_name(request) not in {"", "disabled", "none"}

    def _sandbox_provider_name(self, request: TaskRequest) -> str:
        raw_value = request.sandbox_provider or self.default_sandbox_provider
        return str(raw_value).lower()

    def _sandbox_image(self, request: TaskRequest) -> str:
        image = request.sandbox_image or self.default_sandbox_image
        return image if isinstance(image, str) and image else self.default_sandbox_image

    def _sandbox_network_policy(self, request: TaskRequest) -> NetworkPolicy:
        raw_value = str(
            request.metadata.get("sandbox_network", self.sandbox_network)
        ).lower()
        if raw_value in {"default", "bridge"}:
            return NetworkPolicy.DEFAULT
        if raw_value == "allowlist":
            return NetworkPolicy.ALLOWLIST
        return NetworkPolicy.DISABLED

    def _sandbox_metadata(
        self,
        runtime: TaskSandboxRuntime | None,
        cleanup: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if runtime is None:
            return {"enabled": False}
        return {
            "enabled": True,
            "provider": runtime.provider,
            "id": runtime.info.id,
            "image": runtime.info.image,
            "status": str(runtime.info.status),
            "repository_path": runtime.info.repository_path
            or str(runtime.spec.repository_path),
            "artifacts_path": runtime.info.artifacts_path
            or str(runtime.spec.artifacts_path),
            "healthcheck": {
                "ok": runtime.healthcheck.ok,
                "checks": dict(runtime.healthcheck.checks),
                "details": dict(runtime.healthcheck.details),
            },
            "cleanup": cleanup or {"deleted": None},
        }

    def _classify_task(self, request: TaskRequest) -> TaskProfile | None:
        if self.task_classifier is None:
            return None
        return self.task_classifier.classify(request)

    def _execution_metadata(self, profile: TaskProfile | None) -> dict[str, Any]:
        if profile is None:
            return {"classified": False}
        return {
            "classified": True,
            "mode": profile.mode.value,
            "complexity": profile.complexity.value,
            "phases": [phase.value for phase in profile.phases],
            "reasons": list(profile.reasons),
        }

    def _workspace_metadata(self, layout) -> dict[str, str]:
        return {
            "root": str(layout.root),
            "repository": str(layout.repository),
            "artifacts": str(layout.artifacts),
            "logs": str(layout.logs),
            "metadata": str(layout.metadata),
        }

    def _repository_metadata(
        self,
        prepared_repository: PreparedRepository | None,
        repository_path: Path,
    ) -> dict[str, Any]:
        if prepared_repository is None:
            return {
                "provided": False,
                "path": str(repository_path),
            }
        return {
            "provided": True,
            "path": str(prepared_repository.repository_path),
            "requested_url": prepared_repository.requested_url,
            "requested_ref": prepared_repository.requested_ref,
            "resolved_commit": prepared_repository.resolved_commit,
        }

    def _select_runner(self, profile: TaskProfile | None) -> AgentRunner:
        if profile is None or self.execution_router is None:
            return self.runner
        return self.execution_router.route(profile)

    def _list_artifacts(self, artifact_root: Path) -> list[str]:
        if not artifact_root.exists():
            return []
        return [
            path.relative_to(artifact_root).as_posix()
            for path in sorted(artifact_root.rglob("*"))
            if path.is_file()
        ]
