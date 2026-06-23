from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class SandboxStatus(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"


class NetworkPolicy(StrEnum):
    DISABLED = "disabled"
    DEFAULT = "default"
    ALLOWLIST = "allowlist"


@dataclass(frozen=True)
class ResourceLimits:
    cpu_cores: float | None = 1.0
    memory_limit: str | None = "1g"
    pids_limit: int | None = 128


@dataclass(frozen=True)
class MountSpec:
    source: str | Path
    target: str
    read_only: bool = True

    def source_path(self) -> Path:
        return Path(self.source).resolve()


@dataclass(frozen=True)
class CommandSpec:
    argv: list[str]
    working_directory: str = "/workspace/repository"
    environment: dict[str, str] = field(default_factory=dict)
    stdin: str | None = None
    timeout_seconds: int | None = None
    max_output_bytes: int | None = None

    @classmethod
    def shell(
        cls,
        command: str,
        *,
        working_directory: str = "/workspace/repository",
        timeout_seconds: int | None = None,
        max_output_bytes: int | None = None,
    ) -> "CommandSpec":
        return cls(
            argv=["/bin/sh", "-lc", command],
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )


@dataclass(frozen=True)
class CommandResult:
    sandbox_id: str
    command: list[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
    truncated: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SandboxSpec:
    image: str
    repository_path: str | Path
    artifacts_path: str | Path
    id: str | None = None
    created_by_user_id: str | None = None
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    mounts: list[MountSpec] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    command_timeout_seconds: int = 30
    max_output_bytes: int = 20_000

    # Backward-compatible constructor fields used by the old demo.
    network_disabled: bool | None = None
    cpu_cores: float | None = None
    memory_limit: str | None = None
    pids_limit: int | None = None

    def normalized(self) -> "SandboxSpec":
        network_policy = self.network_policy
        if self.network_disabled is not None:
            network_policy = (
                NetworkPolicy.DISABLED
                if self.network_disabled
                else NetworkPolicy.DEFAULT
            )

        resource_limits = self.resource_limits
        if (
            self.cpu_cores is not None
            or self.memory_limit is not None
            or self.pids_limit is not None
        ):
            resource_limits = ResourceLimits(
                cpu_cores=self.cpu_cores
                if self.cpu_cores is not None
                else resource_limits.cpu_cores,
                memory_limit=self.memory_limit
                if self.memory_limit is not None
                else resource_limits.memory_limit,
                pids_limit=self.pids_limit
                if self.pids_limit is not None
                else resource_limits.pids_limit,
            )

        mounts = list(self.mounts)
        if not mounts:
            mounts = [
                MountSpec(
                    source=self.repository_path,
                    target="/workspace/repository",
                    read_only=True,
                ),
                MountSpec(
                    source=self.artifacts_path,
                    target="/workspace/artifacts",
                    read_only=False,
                ),
            ]

        return SandboxSpec(
            id=self.id,
            image=self.image,
            repository_path=self.repository_path,
            artifacts_path=self.artifacts_path,
            created_by_user_id=self.created_by_user_id,
            network_policy=network_policy,
            resource_limits=resource_limits,
            mounts=mounts,
            environment=dict(self.environment),
            command_timeout_seconds=self.command_timeout_seconds,
            max_output_bytes=self.max_output_bytes,
        )


@dataclass(frozen=True)
class SandboxInfo:
    id: str
    status: SandboxStatus
    image: str
    container_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    repository_path: str | None = None
    artifacts_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = str(self.status)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass(frozen=True)
class SandboxPage:
    items: list[SandboxInfo]
    next_page_id: str | None = None

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {
            "items": [item.model_dump(mode=mode) for item in self.items],
            "next_page_id": self.next_page_id,
        }
