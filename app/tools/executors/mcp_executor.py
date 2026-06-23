from __future__ import annotations

from app.tools.executors.base import ToolExecutor
from app.tools.models import ToolContext, ToolRequest, ToolResult


class MCPExecutor(ToolExecutor):
    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        return ToolResult.failed(
            request,
            "MCP execution is planned for a later implementation phase.",
        )
