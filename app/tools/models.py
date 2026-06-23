from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class ToolRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolExecutionTarget(StrEnum):
    NATIVE = "native"
    MCP = "mcp"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    execution_target: ToolExecutionTarget = ToolExecutionTarget.NATIVE
    requires_write: bool = False
    allowed_roles: set[str] = field(default_factory=set)

    def to_model_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema or {
                    "type": "object",
                    "properties": {},
                },
            },
        }


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"call_{uuid4().hex}")


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    request_id: str
    success: bool
    content: str = ""
    data: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(
        cls,
        request: ToolRequest,
        content: str = "",
        data: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(
            tool_name=request.tool_name,
            request_id=request.id,
            success=True,
            content=content,
            data=data,
            metadata=metadata or {},
        )

    @classmethod
    def failed(
        cls,
        request: ToolRequest,
        error: str,
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(
            tool_name=request.tool_name,
            request_id=request.id,
            success=False,
            content=content or error,
            error=error,
            metadata=metadata or {},
        )

    def to_model_content(self) -> str:
        if self.success:
            return self.content
        return f"Tool {self.tool_name} failed: {self.error or self.content}"


@dataclass(frozen=True)
class ToolContext:
    task_id: str
    workspace_root: str | Path
    role: str = "agent"
    artifact_root: str | Path | None = None
    allowed_paths: tuple[str | Path, ...] = ()
    allow_write: bool = False
    allow_network: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def workspace_path(self) -> Path:
        return Path(self.workspace_root).resolve()

    def artifact_path(self) -> Path:
        if self.artifact_root is None:
            return self.workspace_path() / "artifacts"
        return Path(self.artifact_root).resolve()

    def allowed_roots(self) -> tuple[Path, ...]:
        roots = [self.workspace_path(), self.artifact_path()]
        roots.extend(Path(path).resolve() for path in self.allowed_paths)
        return tuple(dict.fromkeys(roots))


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason: str) -> "PolicyDecision":
        return cls(allowed=False, reason=reason)
