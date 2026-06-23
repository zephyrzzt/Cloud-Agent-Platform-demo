from __future__ import annotations

from pathlib import Path

from app.tools.base import NativeTool
from app.tools.models import (
    ToolContext,
    ToolDefinition,
    ToolRequest,
    ToolResult,
    ToolRiskLevel,
)


def _artifact_path(context: ToolContext, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (context.artifact_path() / path).resolve()


class WriteArtifactTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_artifact",
            description="Write a task artifact under the artifact root.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            risk_level=ToolRiskLevel.MEDIUM,
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        path = _artifact_path(context, request.arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(request.arguments["content"], encoding="utf-8")
        return ToolResult.ok(
            request,
            f"Wrote artifact: {path}",
            data={"path": str(path)},
        )


class ListArtifactsTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_artifacts",
            description="List task artifacts.",
            parameters_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        root = context.artifact_path()
        if not root.exists():
            return ToolResult.ok(request, "", data={"items": []})

        items = [
            path.relative_to(root).as_posix()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]
        return ToolResult.ok(request, "\n".join(items), data={"items": items})


class FinishTaskTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="finish_task",
            description="Declare that the agent believes the task is complete.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["summary"],
                "additionalProperties": False,
            },
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        status = request.arguments.get("status", "completed")
        summary = request.arguments["summary"]
        return ToolResult.ok(
            request,
            summary,
            data={"finished": True, "status": status, "summary": summary},
        )
