from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.sandbox.healthcheck import SandboxHealthcheck
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
from app.sandbox.providers.docker import DockerSandboxService
from app.sandbox.service import SandboxService
from app.workspace.repository_preparer import RepositoryPreparer, RepositorySpec
from app.workspace.workspace_manager import WorkspaceManager, WorkspacePathError


class SecondPhaseTests(unittest.TestCase):
    def test_workspace_manager_creates_expected_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(tmp)
            layout = manager.create_workspace("task-1")

            self.assertTrue(layout.repository.is_dir())
            self.assertTrue(layout.artifacts.is_dir())
            self.assertTrue(layout.logs.is_dir())
            self.assertTrue(layout.metadata.is_dir())
            self.assertEqual(layout.resolve_inside("repository"), layout.repository)

    def test_workspace_manager_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(tmp)
            layout = manager.create_workspace("task-1")

            with self.assertRaises(WorkspacePathError):
                layout.resolve_inside("../outside")

    def test_repository_preparer_clones_local_repository(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            self._git(["init"], cwd=source)
            (source / "README.md").write_text("hello", encoding="utf-8")
            self._git(["add", "README.md"], cwd=source)
            self._git(
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

            prepared = RepositoryPreparer().prepare(
                RepositorySpec(url=str(source), depth=None),
                destination,
            )

            self.assertTrue((prepared.repository_path / "README.md").is_file())
            self.assertIsNotNone(prepared.resolved_commit)

    def test_sandbox_policy_normalizes_and_validates_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repository = root / "repo"
            artifacts = root / "artifacts"
            repository.mkdir()
            artifacts.mkdir()

            policy = SandboxPolicy(allowed_images={"cloud-agent-sandbox:latest"})
            spec = policy.validate_spec(
                SandboxSpec(
                    image="cloud-agent-sandbox:latest",
                    repository_path=repository,
                    artifacts_path=artifacts,
                    network_disabled=True,
                    cpu_cores=0.5,
                    memory_limit="512m",
                    pids_limit=64,
                )
            )

            self.assertEqual(spec.network_policy, NetworkPolicy.DISABLED)
            self.assertEqual(spec.resource_limits.cpu_cores, 0.5)
            self.assertEqual(len(spec.mounts), 2)
            self.assertTrue(spec.mounts[0].read_only)
            self.assertFalse(spec.mounts[1].read_only)

    def test_docker_provider_builds_isolated_run_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repository = root / "repo"
            artifacts = root / "artifacts"
            repository.mkdir()
            artifacts.mkdir()
            service = DockerSandboxService()
            spec = SandboxSpec(
                image="cloud-agent-sandbox:latest",
                repository_path=repository,
                artifacts_path=artifacts,
            ).normalized()

            command = service._docker_run_command(spec, "abc")

            self.assertIn("--network", command)
            self.assertIn("none", command)
            self.assertIn("--read-only", command)
            self.assertIn("--cap-drop", command)
            self.assertTrue(any("target=/workspace/repository,ro" in item for item in command))
            self.assertTrue(any("target=/workspace/artifacts,rw" in item for item in command))

    def test_healthcheck_runs_expected_checks(self) -> None:
        service = FakeSandboxService()
        result = asyncio.run(SandboxHealthcheck(required_tools=["git"]).run(service, "s1"))

        self.assertTrue(result.ok)
        self.assertTrue(result.checks["repository_dir"])
        self.assertTrue(result.checks["artifacts_dir"])
        self.assertTrue(result.checks["non_root_user"])
        self.assertTrue(result.checks["tool:git"])

    def _git(self, args: list[str], *, cwd: Path) -> None:
        subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )


class FakeSandboxService(SandboxService):
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
        return SandboxInfo(
            id=sandbox_id or "fake",
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
        command_spec = command if isinstance(command, CommandSpec) else CommandSpec(argv=list(command))
        return CommandResult(
            sandbox_id=sandbox_id,
            command=command_spec.argv,
            exit_code=0,
            stdout="ok",
        )

    async def pause_sandbox(self, sandbox_id: str) -> bool:
        return True

    async def resume_sandbox(self, sandbox_id: str) -> bool:
        return True

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        return True


if __name__ == "__main__":
    unittest.main()
