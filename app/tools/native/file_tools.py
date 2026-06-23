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


def _resolve_workspace_path(context: ToolContext, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = context.workspace_path() / path
    return path.resolve()


class ListFilesTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_files",
            description="List files and directories under a workspace path.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_depth": {"type": "integer"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        root = _resolve_workspace_path(context, request.arguments["path"])
        max_depth = request.arguments.get("max_depth", 1)
        if not root.exists():
            return ToolResult.failed(request, f"Path does not exist: {root}")
        if not root.is_dir():
            return ToolResult.failed(request, f"Path is not a directory: {root}")

        rows: list[str] = []
        for item in sorted(root.rglob("*")):
            depth = len(item.relative_to(root).parts)
            if depth > max_depth:
                continue
            marker = "/" if item.is_dir() else ""
            rows.append(f"{item.relative_to(root).as_posix()}{marker}")

        return ToolResult.ok(request, "\n".join(rows), data={"items": rows})


class ReadFileTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read a UTF-8 text file from the workspace.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        path = _resolve_workspace_path(context, request.arguments["path"])
        max_chars = request.arguments.get("max_chars")
        if not path.exists():
            return ToolResult.failed(request, f"File does not exist: {path}")
        if not path.is_file():
            return ToolResult.failed(request, f"Path is not a file: {path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        truncated = False
        if max_chars is not None and len(content) > max_chars:
            content = content[:max_chars]
            truncated = True

        return ToolResult.ok(
            request,
            content,
            data={"path": str(path), "truncated": truncated},
        )


class WriteFileTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write a UTF-8 text file inside the workspace.",
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
            requires_write=True,
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        path = _resolve_workspace_path(context, request.arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(request.arguments["content"], encoding="utf-8")
        return ToolResult.ok(request, f"Wrote file: {path}", data={"path": str(path)})


class EditFileTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit_file",
            description="Replace text in a UTF-8 workspace file.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
            risk_level=ToolRiskLevel.MEDIUM,
            requires_write=True,
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        path = _resolve_workspace_path(context, request.arguments["path"])
        if not path.exists():
            return ToolResult.failed(request, f"File does not exist: {path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        old_text = request.arguments["old_text"]
        if old_text not in content:
            return ToolResult.failed(request, "old_text was not found")

        updated = content.replace(old_text, request.arguments["new_text"], 1)
        path.write_text(updated, encoding="utf-8")
        return ToolResult.ok(request, f"Edited file: {path}", data={"path": str(path)})
