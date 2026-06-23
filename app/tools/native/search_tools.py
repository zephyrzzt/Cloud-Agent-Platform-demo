from __future__ import annotations

import re
from pathlib import Path

from app.tools.base import NativeTool
from app.tools.models import ToolContext, ToolDefinition, ToolRequest, ToolResult


class SearchCodeTool(NativeTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_code",
            description="Search text files in the workspace with a regular expression.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        query = request.arguments["query"]
        root = self._resolve_root(context, request.arguments.get("path", "."))
        max_results = request.arguments.get("max_results", 50)
        if not root.exists():
            return ToolResult.failed(request, f"Path does not exist: {root}")

        pattern = re.compile(query)
        matches: list[dict] = []
        files = [root] if root.is_file() else root.rglob("*")
        for path in files:
            if len(matches) >= max_results:
                break
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError:
                continue

            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    matches.append(
                        {
                            "path": str(path),
                            "line": line_number,
                            "text": line,
                        }
                    )
                    if len(matches) >= max_results:
                        break

        content = "\n".join(
            f"{item['path']}:{item['line']}: {item['text']}" for item in matches
        )
        return ToolResult.ok(request, content, data={"matches": matches})

    def _resolve_root(self, context: ToolContext, raw_path: str) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = context.workspace_path() / path
        return path.resolve()
