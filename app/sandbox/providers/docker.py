from __future__ import annotations

import asyncio
import json
import subprocess
import time
from datetime import datetime, timezone
from uuid import uuid4

from app.sandbox.errors import (
    SandboxExecutionError,
    SandboxNotFoundError,
    SandboxStartError,
)
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
from app.sandbox.service import SandboxService, coerce_command_spec


class DockerSandboxService(SandboxService):
    def __init__(
        self,
        *,
        policy: SandboxPolicy | None = None,
        docker_binary: str = "docker",
        name_prefix: str = "cloud-agent",
        max_num_sandboxes: int | None = None,
    ) -> None:
        self.policy = policy or SandboxPolicy()
        self.docker_binary = docker_binary
        self.name_prefix = name_prefix
        self.max_num_sandboxes = max_num_sandboxes
        self._specs: dict[str, SandboxSpec] = {}

    async def search_sandboxes(
        self,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxPage:
        result = await self._run_docker(
            [
                "ps",
                "-a",
                "--filter",
                "label=cloud-agent.sandbox=true",
                "--format",
                "{{json .}}",
            ],
            check=False,
        )
        items: list[SandboxInfo] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            sandbox_id = raw.get("Names", "")
            if sandbox_id.startswith(f"{self.name_prefix}-"):
                sandbox_id = sandbox_id[len(self.name_prefix) + 1 :]
            info = await self.get_sandbox(sandbox_id)
            if info is not None:
                items.append(info)
        return SandboxPage(items=items[:limit], next_page_id=None)

    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo | None:
        container_name = self._container_name(sandbox_id)
        result = await self._run_docker(["inspect", container_name], check=False)
        if result.returncode != 0:
            return None

        try:
            raw = json.loads(result.stdout)[0]
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

        state = raw.get("State", {})
        labels = raw.get("Config", {}).get("Labels", {}) or {}
        spec = self._specs.get(sandbox_id)

        return SandboxInfo(
            id=sandbox_id,
            status=self._status_from_docker(state),
            image=raw.get("Config", {}).get("Image", ""),
            container_id=raw.get("Id"),
            created_at=self._parse_created_at(raw.get("Created")),
            repository_path=str(spec.repository_path)
            if spec
            else labels.get("cloud-agent.repository"),
            artifacts_path=str(spec.artifacts_path)
            if spec
            else labels.get("cloud-agent.artifacts"),
            metadata={"container_name": container_name},
        )

    async def start_sandbox(
        self,
        spec: SandboxSpec,
        sandbox_id: str | None = None,
    ) -> SandboxInfo:
        normalized = self.policy.validate_spec(spec)
        sandbox_id = sandbox_id or normalized.id or uuid4().hex
        if self.max_num_sandboxes is not None:
            await self._enforce_max_sandboxes()

        result = await self._run_docker(
            self._docker_run_command(normalized, sandbox_id),
            check=False,
        )
        if result.returncode != 0:
            raise SandboxStartError(result.stderr.strip() or "docker run failed")

        self._specs[sandbox_id] = normalized
        sandbox = await self.get_sandbox(sandbox_id)
        if sandbox is None:
            raise SandboxStartError("docker container cannot be inspected")
        return sandbox

    async def execute(
        self,
        sandbox_id: str,
        command: CommandSpec | list[str] | str,
        workdir: str = "/workspace/repository",
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        sandbox = await self.get_sandbox(sandbox_id)
        if sandbox is None:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")
        if sandbox.status != SandboxStatus.RUNNING:
            raise SandboxExecutionError(f"Sandbox is not running: {sandbox_id}")

        spec = self._specs.get(sandbox_id)
        if spec is None:
            raise SandboxExecutionError(f"Sandbox spec is not tracked: {sandbox_id}")

        command_spec = coerce_command_spec(
            command,
            workdir=workdir,
            timeout_seconds=timeout_seconds,
        )
        command_spec = self.policy.validate_command(command_spec, spec)
        started_at = time.monotonic()

        docker_command = ["exec", "-i", "-w", command_spec.working_directory]
        for key, value in command_spec.environment.items():
            docker_command.extend(["--env", f"{key}={value}"])
        docker_command.append(self._container_name(sandbox_id))
        docker_command.extend(command_spec.argv)

        try:
            result = await self._run_docker(
                docker_command,
                input_text=command_spec.stdin,
                timeout=command_spec.timeout_seconds,
                check=False,
            )
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stdout = self._decode_timeout_output(exc.stdout)
            stderr = self._decode_timeout_output(exc.stderr)
            return CommandResult(
                sandbox_id=sandbox_id,
                command=command_spec.argv,
                exit_code=124,
                stdout=self._truncate(stdout, command_spec.max_output_bytes)[0],
                stderr=self._truncate(stderr, command_spec.max_output_bytes)[0],
                timed_out=True,
                duration_seconds=time.monotonic() - started_at,
                truncated=True,
            )

        stdout, stdout_truncated = self._truncate(
            result.stdout,
            command_spec.max_output_bytes,
        )
        stderr, stderr_truncated = self._truncate(
            result.stderr,
            command_spec.max_output_bytes,
        )
        return CommandResult(
            sandbox_id=sandbox_id,
            command=command_spec.argv,
            exit_code=result.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_seconds=time.monotonic() - started_at,
            truncated=stdout_truncated or stderr_truncated,
        )

    async def pause_sandbox(self, sandbox_id: str) -> bool:
        result = await self._run_docker(
            ["pause", self._container_name(sandbox_id)],
            check=False,
        )
        return result.returncode == 0

    async def resume_sandbox(self, sandbox_id: str) -> bool:
        result = await self._run_docker(
            ["unpause", self._container_name(sandbox_id)],
            check=False,
        )
        return result.returncode == 0

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        result = await self._run_docker(
            ["rm", "-f", self._container_name(sandbox_id)],
            check=False,
        )
        self._specs.pop(sandbox_id, None)
        return result.returncode == 0

    async def is_available(self) -> bool:
        result = await self._run_docker(
            ["version", "--format", "{{.Server.Version}}"],
            check=False,
        )
        return result.returncode == 0

    def _docker_run_command(self, spec: SandboxSpec, sandbox_id: str) -> list[str]:
        args = [
            "run",
            "-d",
            "--name",
            self._container_name(sandbox_id),
            "--label",
            "cloud-agent.sandbox=true",
            "--label",
            f"cloud-agent.sandbox_id={sandbox_id}",
            "--label",
            f"cloud-agent.repository={spec.repository_path}",
            "--label",
            f"cloud-agent.artifacts={spec.artifacts_path}",
            "--user",
            "1000:1000",
            "--workdir",
            "/workspace/repository",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
        ]

        if spec.network_policy == NetworkPolicy.DISABLED:
            args.extend(["--network", "none"])

        limits = spec.resource_limits
        if limits.cpu_cores is not None:
            args.extend(["--cpus", str(limits.cpu_cores)])
        if limits.memory_limit is not None:
            args.extend(["--memory", limits.memory_limit])
        if limits.pids_limit is not None:
            args.extend(["--pids-limit", str(limits.pids_limit)])

        for key, value in spec.environment.items():
            args.extend(["--env", f"{key}={value}"])

        for mount in spec.mounts:
            mode = "ro" if mount.read_only else "rw"
            args.extend(
                [
                    "--mount",
                    (
                        f"type=bind,source={mount.source_path()},"
                        f"target={mount.target},{mode}"
                    ),
                ]
            )

        args.extend([spec.image, "sleep", "infinity"])
        return args

    async def _enforce_max_sandboxes(self) -> None:
        assert self.max_num_sandboxes is not None
        page = await self.search_sandboxes(limit=1000)
        running = [item for item in page.items if item.status == SandboxStatus.RUNNING]
        if len(running) < self.max_num_sandboxes:
            return
        running.sort(key=lambda item: item.created_at)
        for item in running[: len(running) - self.max_num_sandboxes + 1]:
            await self.pause_sandbox(item.id)

    async def _run_docker(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        timeout: int | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return await asyncio.to_thread(
                subprocess.run,
                [self.docker_binary, *args],
                input=input_text,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=check,
            )
        except FileNotFoundError as exc:
            raise SandboxStartError("docker executable was not found") from exc

    def _container_name(self, sandbox_id: str) -> str:
        return f"{self.name_prefix}-{sandbox_id}"

    def _status_from_docker(self, state: dict) -> SandboxStatus:
        if state.get("Paused"):
            return SandboxStatus.PAUSED
        if state.get("Running"):
            return SandboxStatus.RUNNING
        if state.get("Status") == "created":
            return SandboxStatus.CREATED
        if state.get("Dead") or state.get("Error"):
            return SandboxStatus.ERROR
        return SandboxStatus.STOPPED

    def _parse_created_at(self, value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    def _truncate(self, value: str, max_bytes: int | None) -> tuple[str, bool]:
        if max_bytes is None:
            return value, False
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return value, False
        return encoded[:max_bytes].decode("utf-8", errors="replace"), True

    def _decode_timeout_output(self, value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
