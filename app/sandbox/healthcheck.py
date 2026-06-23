from __future__ import annotations

from dataclasses import dataclass, field

from app.sandbox.models import CommandSpec
from app.sandbox.service import SandboxService


@dataclass(frozen=True)
class HealthcheckResult:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)


class SandboxHealthcheck:
    def __init__(self, required_tools: list[str] | None = None) -> None:
        self.required_tools = required_tools or ["git", "rg", "python"]

    async def run(
        self,
        service: SandboxService,
        sandbox_id: str,
    ) -> HealthcheckResult:
        checks: dict[str, bool] = {}
        details: dict[str, str] = {}

        checks["repository_dir"] = await self._check_command(
            service,
            sandbox_id,
            ["test", "-d", "/workspace/repository"],
            details,
        )
        checks["artifacts_dir"] = await self._check_command(
            service,
            sandbox_id,
            ["test", "-d", "/workspace/artifacts"],
            details,
        )
        checks["non_root_user"] = await self._check_command(
            service,
            sandbox_id,
            ["/bin/sh", "-lc", "test \"$(id -u)\" != \"0\""],
            details,
        )

        for tool in self.required_tools:
            checks[f"tool:{tool}"] = await self._check_command(
                service,
                sandbox_id,
                ["/bin/sh", "-lc", f"command -v {tool}"],
                details,
            )

        return HealthcheckResult(ok=all(checks.values()), checks=checks, details=details)

    async def _check_command(
        self,
        service: SandboxService,
        sandbox_id: str,
        argv: list[str],
        details: dict[str, str],
    ) -> bool:
        result = await service.execute(
            sandbox_id,
            CommandSpec(argv=argv, timeout_seconds=5, max_output_bytes=2_000),
        )
        if not result.success:
            details[" ".join(argv)] = result.stderr or result.stdout
        return result.success
