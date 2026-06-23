from __future__ import annotations

from app.sandbox.errors import SandboxStartError
from app.sandbox.models import CommandResult, SandboxInfo, SandboxPage, SandboxSpec
from app.sandbox.service import SandboxService


class FirecrackerSandboxService(SandboxService):
    async def search_sandboxes(
        self,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxPage:
        return SandboxPage(items=[])

    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo | None:
        return None

    async def start_sandbox(
        self,
        spec: SandboxSpec,
        sandbox_id: str | None = None,
    ) -> SandboxInfo:
        raise SandboxStartError("Firecracker sandbox provider is not enabled yet")

    async def execute(
        self,
        sandbox_id: str,
        command,
        workdir: str = "/workspace/repository",
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        raise SandboxStartError("Firecracker sandbox provider is not enabled yet")

    async def pause_sandbox(self, sandbox_id: str) -> bool:
        return False

    async def resume_sandbox(self, sandbox_id: str) -> bool:
        return False

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        return False
