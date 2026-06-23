from __future__ import annotations

from abc import ABC, abstractmethod

from app.tools.models import ToolContext, ToolDefinition, ToolRequest, ToolResult


class ToolError(RuntimeError):
    pass


class NativeTool(ABC):
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        raise NotImplementedError

    def validate(self, arguments: dict) -> None:
        return None

    @abstractmethod
    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        raise NotImplementedError
