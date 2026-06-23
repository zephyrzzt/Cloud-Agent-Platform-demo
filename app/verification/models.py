from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.domain.task import TaskRequest
from app.orchestration.agent_loop import AgentLoopResult


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: list[VerificationCheck] = field(default_factory=list)
    summary: str = ""

    @property
    def failed_checks(self) -> list[VerificationCheck]:
        return [check for check in self.checks if not check.passed]

    @property
    def error_summary(self) -> str:
        if self.passed:
            return ""
        if self.summary:
            return self.summary
        return "; ".join(check.message for check in self.failed_checks if check.message)

    def model_dump(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "checks": [check.model_dump() for check in self.checks],
        }


@dataclass(frozen=True)
class VerificationContext:
    task_request: TaskRequest
    workspace_root: Path
    artifact_root: Path
    artifact_paths: list[str]
    loop_result: AgentLoopResult
