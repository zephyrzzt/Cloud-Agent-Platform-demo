from __future__ import annotations

from app.tools.executors.base import ToolExecutor
from app.tools.models import ToolContext, ToolExecutionTarget, ToolRequest, ToolResult
from app.tools.registry import ToolRegistry


class ExecutorRouter(ToolExecutor):
    def __init__(
        self,
        registry: ToolRegistry,
        native_executor: ToolExecutor,
        mcp_executor: ToolExecutor | None = None,
    ) -> None:
        self.registry = registry
        self.native_executor = native_executor
        self.mcp_executor = mcp_executor

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        definition = self.registry.get_definition(request.tool_name)
        if definition.execution_target == ToolExecutionTarget.NATIVE:
            return await self.native_executor.execute(request, context)

        if definition.execution_target == ToolExecutionTarget.MCP and self.mcp_executor:
            return await self.mcp_executor.execute(request, context)

        return ToolResult.failed(
            request,
            f"No executor configured for target: {definition.execution_target}",
        )
