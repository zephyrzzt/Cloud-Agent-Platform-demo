from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod

from app.sandbox.errors import SandboxError, SandboxNotFoundError
from app.sandbox.models import (
    CommandResult,
    CommandSpec,
    SandboxInfo,
    SandboxPage,
    SandboxSpec,
    SandboxStatus,
)


class SandboxService(ABC):
    @abstractmethod
    async def search_sandboxes(
        self,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxPage:
        raise NotImplementedError

    @abstractmethod
    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo | None:
        raise NotImplementedError

    @abstractmethod
    async def start_sandbox(
        self,
        spec: SandboxSpec,
        sandbox_id: str | None = None,
    ) -> SandboxInfo:
        raise NotImplementedError

    @abstractmethod
    async def execute(
        self,
        sandbox_id: str,
        command: CommandSpec | list[str] | str,
        workdir: str = "/workspace/repository",
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        raise NotImplementedError

    @abstractmethod
    async def pause_sandbox(self, sandbox_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def resume_sandbox(self, sandbox_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def delete_sandbox(self, sandbox_id: str) -> bool:
        raise NotImplementedError

    async def wait_until_ready(
        self,
        sandbox_id: str,
        timeout: int = 30,
        poll_interval: float = 0.5,
    ) -> SandboxInfo:
        started_at = time.monotonic()
        while time.monotonic() - started_at <= timeout:
            sandbox = await self.get_sandbox(sandbox_id)
            if sandbox is None:
                raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")
            if sandbox.status == SandboxStatus.RUNNING:
                return sandbox
            if sandbox.status == SandboxStatus.ERROR:
                raise SandboxError(f"Sandbox entered error state: {sandbox_id}")
            await asyncio.sleep(poll_interval)
        raise SandboxError(f"Sandbox did not become ready within {timeout} seconds")

    async def wait_for_sandbox_running(
        self,
        sandbox_id: str,
        timeout: int = 30,
        poll_interval: float = 0.5,
    ) -> SandboxInfo:
        return await self.wait_until_ready(sandbox_id, timeout, poll_interval)


def coerce_command_spec(
    command: CommandSpec | list[str] | str,
    *,
    workdir: str = "/workspace/repository",
    timeout_seconds: int | None = None,
) -> CommandSpec:
    if isinstance(command, CommandSpec):
        return command
    if isinstance(command, str):
        return CommandSpec.shell(
            command,
            working_directory=workdir,
            timeout_seconds=timeout_seconds,
        )
    return CommandSpec(
        argv=list(command),
        working_directory=workdir,
        timeout_seconds=timeout_seconds,
    )
