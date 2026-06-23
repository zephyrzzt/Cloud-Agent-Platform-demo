from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import PurePosixPath

from app.sandbox.errors import SandboxPolicyViolationError
from app.sandbox.models import CommandSpec, NetworkPolicy, SandboxSpec


ENV_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True)
class SandboxPolicy:
    allowed_images: set[str] = field(default_factory=set)
    allowed_environment: set[str] = field(default_factory=set)
    default_timeout_seconds: int = 30
    max_timeout_seconds: int = 300
    default_max_output_bytes: int = 20_000
    max_output_bytes: int = 1_000_000
    allow_network: bool = False
    allowed_workdirs: tuple[str, ...] = (
        "/workspace/repository",
        "/workspace/artifacts",
    )

    def validate_spec(self, spec: SandboxSpec) -> SandboxSpec:
        normalized = spec.normalized()

        if self.allowed_images and normalized.image not in self.allowed_images:
            raise SandboxPolicyViolationError(
                f"Sandbox image is not allowed: {normalized.image}"
            )

        if normalized.network_policy != NetworkPolicy.DISABLED and not self.allow_network:
            raise SandboxPolicyViolationError("Sandbox network access is not allowed")

        for mount in normalized.mounts:
            source = mount.source_path()
            if not source.exists():
                raise SandboxPolicyViolationError(
                    f"Mount source does not exist: {source}"
                )

        for key in normalized.environment:
            self._validate_environment_name(key)
            if self.allowed_environment and key not in self.allowed_environment:
                raise SandboxPolicyViolationError(
                    f"Environment variable is not allowed: {key}"
                )

        if normalized.command_timeout_seconds > self.max_timeout_seconds:
            raise SandboxPolicyViolationError("Command timeout exceeds policy maximum")

        if normalized.max_output_bytes > self.max_output_bytes:
            raise SandboxPolicyViolationError("Command output limit exceeds policy maximum")

        return normalized

    def validate_command(self, command: CommandSpec, spec: SandboxSpec) -> CommandSpec:
        if not command.argv:
            raise SandboxPolicyViolationError("Command argv cannot be empty")

        for value in command.argv:
            if not isinstance(value, str) or not value:
                raise SandboxPolicyViolationError("Command argv must contain strings")

        for key in command.environment:
            self._validate_environment_name(key)
            if self.allowed_environment and key not in self.allowed_environment:
                raise SandboxPolicyViolationError(
                    f"Environment variable is not allowed: {key}"
                )

        timeout = command.timeout_seconds or spec.command_timeout_seconds
        if timeout <= 0 or timeout > self.max_timeout_seconds:
            raise SandboxPolicyViolationError("Command timeout is outside policy")

        max_output = command.max_output_bytes or spec.max_output_bytes
        if max_output <= 0 or max_output > self.max_output_bytes:
            raise SandboxPolicyViolationError("Command output limit is outside policy")

        self._validate_workdir(command.working_directory)

        return CommandSpec(
            argv=list(command.argv),
            working_directory=command.working_directory,
            environment=dict(command.environment),
            stdin=command.stdin,
            timeout_seconds=timeout,
            max_output_bytes=max_output,
        )

    def _validate_workdir(self, workdir: str) -> None:
        path = PurePosixPath(workdir)
        if not path.is_absolute() or ".." in path.parts:
            raise SandboxPolicyViolationError(
                f"Command workdir is not allowed: {workdir}"
            )

        for raw_root in self.allowed_workdirs:
            root = PurePosixPath(raw_root)
            if path == root or path.is_relative_to(root):
                return

        raise SandboxPolicyViolationError(f"Command workdir is not allowed: {workdir}")

    def _validate_environment_name(self, key: str) -> None:
        if not ENV_NAME_PATTERN.fullmatch(key):
            raise SandboxPolicyViolationError(
                f"Invalid environment variable name: {key}"
            )

    def assert_path_allowed(self, path: str | Path, roots: list[Path]) -> Path:
        resolved = Path(path).resolve()
        for root in roots:
            try:
                resolved.relative_to(root.resolve())
                return resolved
            except ValueError:
                continue
        raise SandboxPolicyViolationError(f"Path is outside allowed roots: {path}")
