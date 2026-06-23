from __future__ import annotations

from app.tools.executors.base import ToolExecutor
from app.tools.models import ToolContext, ToolRequest, ToolResult
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolNotFoundError, ToolRegistry
from app.tools.validator import ToolValidationError, ToolValidator


class NativeExecutor(ToolExecutor):
    def __init__(
        self,
        registry: ToolRegistry,
        validator: ToolValidator | None = None,
        policy: ToolPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.validator = validator or ToolValidator()
        self.policy = policy or ToolPolicy()

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        try:
            tool = self.registry.get_tool(request.tool_name)
        except ToolNotFoundError as exc:
            return ToolResult.failed(request, str(exc))

        definition = tool.definition

        try:
            self.validator.validate_request(request, definition)
            tool.validate(request.arguments)
        except ToolValidationError as exc:
            return ToolResult.failed(request, str(exc))
        except ValueError as exc:
            return ToolResult.failed(request, str(exc))

        decision = self.policy.evaluate(request, definition, context)
        if not decision.allowed:
            return ToolResult.failed(
                request,
                decision.reason,
                metadata={"policy_denied": True},
            )

        try:
            return await tool.execute(request, context)
        except Exception as exc:
            return ToolResult.failed(request, f"{type(exc).__name__}: {exc}")
