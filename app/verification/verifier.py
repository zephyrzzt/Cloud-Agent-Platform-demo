from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.tools.native.command_tools import CONTROLLED_COMMAND_TOOLS
from app.verification.models import (
    VerificationCheck,
    VerificationContext,
    VerificationResult,
)


class VerificationService(ABC):
    @abstractmethod
    async def verify(self, context: VerificationContext) -> VerificationResult:
        raise NotImplementedError


class BasicVerificationService(VerificationService):
    ARTIFACT_KEYWORDS = {
        "artifact",
        "artifacts",
        "create",
        "document",
        "file",
        "generate",
        "output",
        "persist",
        "report",
        "result",
        "save",
        "summary",
        "write",
    }
    COMMAND_KEYWORDS = {
        "build",
        "command",
        "compile",
        "execute",
        "lint",
        "npm test",
        "program",
        "pytest",
        "python --version",
        "run",
        "test",
        "tests",
    }

    async def verify(self, context: VerificationContext) -> VerificationResult:
        checks = [
            self._check_agent_completed(context),
            self._check_completion_evidence(context),
            self._check_artifacts(context),
            self._check_command_execution(context),
        ]
        passed = all(check.passed for check in checks)
        summary = (
            "Verification passed."
            if passed
            else "Verification failed: "
            + "; ".join(check.message for check in checks if not check.passed)
        )
        return VerificationResult(passed=passed, checks=checks, summary=summary)

    def _check_agent_completed(
        self,
        context: VerificationContext,
    ) -> VerificationCheck:
        if context.loop_result.completed:
            return VerificationCheck(
                name="agent_completed",
                passed=True,
                message=f"Agent ended with status {context.loop_result.status}.",
            )
        return VerificationCheck(
            name="agent_completed",
            passed=False,
            message=f"Agent did not complete: {context.loop_result.status}.",
        )

    def _check_completion_evidence(
        self,
        context: VerificationContext,
    ) -> VerificationCheck:
        requires_tool_backed_completion = (
            self._expects_artifact(context)
            or self._expects_command(context)
            or bool(context.loop_result.tool_results)
        )
        finished = self._has_successful_tool(context, "finish_task")

        if finished:
            return VerificationCheck(
                name="completion_evidence",
                passed=True,
                message="finish_task completed successfully.",
            )

        if not requires_tool_backed_completion and context.loop_result.completed:
            return VerificationCheck(
                name="completion_evidence",
                passed=True,
                message="Text-only completion accepted for this task.",
            )

        return VerificationCheck(
            name="completion_evidence",
            passed=False,
            message="Task requires successful finish_task evidence.",
        )

    def _check_artifacts(self, context: VerificationContext) -> VerificationCheck:
        expected_artifacts = self._expected_artifacts(context)
        expects_artifact = self._expects_artifact(context) or bool(expected_artifacts)
        if not expects_artifact:
            return VerificationCheck(
                name="artifacts",
                passed=True,
                message="No artifact requirement detected.",
            )

        if expected_artifacts:
            missing = [
                path
                for path in expected_artifacts
                if path not in context.artifact_paths
                or not self._artifact_exists(context.artifact_root, path)
            ]
            if missing:
                return VerificationCheck(
                    name="artifacts",
                    passed=False,
                    message="Missing expected artifact(s): " + ", ".join(missing),
                    metadata={"expected": expected_artifacts},
                )
            return VerificationCheck(
                name="artifacts",
                passed=True,
                message="Expected artifacts were produced.",
                metadata={"expected": expected_artifacts},
            )

        existing = [
            path
            for path in context.artifact_paths
            if self._artifact_exists(context.artifact_root, path)
        ]
        if existing:
            return VerificationCheck(
                name="artifacts",
                passed=True,
                message="At least one artifact was produced.",
                metadata={"artifacts": existing},
            )
        return VerificationCheck(
            name="artifacts",
            passed=False,
            message="Task appears to require an artifact, but none were produced.",
        )

    def _check_command_execution(
        self,
        context: VerificationContext,
    ) -> VerificationCheck:
        if not self._expects_command(context):
            return VerificationCheck(
                name="command_execution",
                passed=True,
                message="No command execution requirement detected.",
            )

        successful_commands = [
            result
            for result in context.loop_result.tool_results
            if result.tool_name in CONTROLLED_COMMAND_TOOLS and result.success
        ]
        if successful_commands:
            return VerificationCheck(
                name="command_execution",
                passed=True,
                message="A controlled sandbox command completed successfully.",
                metadata={"count": len(successful_commands)},
            )

        return VerificationCheck(
            name="command_execution",
            passed=False,
            message=(
                "Task appears to require command execution, but no controlled "
                "command tool succeeded."
            ),
        )

    def _expects_artifact(self, context: VerificationContext) -> bool:
        metadata_value = context.task_request.metadata.get("requires_artifact")
        if isinstance(metadata_value, bool):
            return metadata_value
        return self._contains_keyword(
            context.task_request.prompt,
            self.ARTIFACT_KEYWORDS,
        )

    def _expects_command(self, context: VerificationContext) -> bool:
        metadata_value = context.task_request.metadata.get("requires_command")
        if isinstance(metadata_value, bool):
            return metadata_value
        return self._contains_keyword(
            context.task_request.prompt,
            self.COMMAND_KEYWORDS,
        )

    def _expected_artifacts(self, context: VerificationContext) -> list[str]:
        raw_value = context.task_request.metadata.get("expected_artifacts")
        if isinstance(raw_value, list):
            return [item for item in raw_value if isinstance(item, str) and item]
        return []

    def _artifact_exists(self, artifact_root: Path, relative_path: str) -> bool:
        candidate = (artifact_root / relative_path).resolve()
        try:
            candidate.relative_to(artifact_root.resolve())
        except ValueError:
            return False
        return candidate.is_file()

    def _has_successful_tool(
        self,
        context: VerificationContext,
        tool_name: str,
    ) -> bool:
        return any(
            result.tool_name == tool_name and result.success
            for result in context.loop_result.tool_results
        )

    def _contains_keyword(self, text: str, keywords: set[str]) -> bool:
        normalized = text.lower()
        return any(keyword in normalized for keyword in keywords)
