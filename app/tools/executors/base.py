from __future__ import annotations

from abc import ABC, abstractmethod

from app.tools.models import ToolContext, ToolRequest, ToolResult


class ToolExecutor(ABC):
    @abstractmethod
    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        raise NotImplementedError
