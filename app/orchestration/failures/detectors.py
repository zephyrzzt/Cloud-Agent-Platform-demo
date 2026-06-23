from __future__ import annotations

from app.orchestration.failures.fingerprint import FailureFingerprinter
from app.orchestration.failures.models import FailureKind, FailureRecord
from app.tools.models import ToolResult


class FailureDetector:
    def __init__(self, fingerprinter: FailureFingerprinter | None = None) -> None:
        self.fingerprinter = fingerprinter or FailureFingerprinter()

    def from_tool_result(
        self,
        *,
        task_id: str,
        result: ToolResult,
    ) -> FailureRecord | None:
        if result.success:
            return None
        kind = FailureKind.POLICY if result.metadata.get("policy_denied") else FailureKind.TOOL
        message = result.error or result.content
        return FailureRecord(
            task_id=task_id,
            kind=kind,
            message=message,
            source=result.tool_name,
            fingerprint=self.fingerprinter.fingerprint(
                kind=kind,
                message=message,
                source=result.tool_name,
            ),
        )

    def from_text(
        self,
        *,
        task_id: str,
        message: str,
        source: str | None = None,
    ) -> FailureRecord:
        lower = message.lower()
        if "assert" in lower or "failed" in lower:
            kind = FailureKind.TEST
        elif "compile" in lower or "build" in lower:
            kind = FailureKind.BUILD
        elif "permission" in lower or "denied" in lower:
            kind = FailureKind.POLICY
        else:
            kind = FailureKind.UNKNOWN
        return FailureRecord(
            task_id=task_id,
            kind=kind,
            message=message,
            source=source,
            fingerprint=self.fingerprinter.fingerprint(
                kind=kind,
                message=message,
                source=source,
            ),
        )
