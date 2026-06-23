from __future__ import annotations

from collections.abc import Iterable

from app.tools.base import NativeTool
from app.tools.models import ToolDefinition


class ToolRegistryError(RuntimeError):
    pass


class ToolNotFoundError(ToolRegistryError):
    pass


class DuplicateToolError(ToolRegistryError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._native_tools: dict[str, NativeTool] = {}

    def register(self, tool: NativeTool, *, replace: bool = False) -> None:
        name = tool.definition.name
        if not replace and name in self._native_tools:
            raise DuplicateToolError(f"Tool already registered: {name}")
        self._native_tools[name] = tool

    def register_many(
        self,
        tools: Iterable[NativeTool],
        *,
        replace: bool = False,
    ) -> None:
        for tool in tools:
            self.register(tool, replace=replace)

    def get_tool(self, name: str) -> NativeTool:
        try:
            return self._native_tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Tool not found: {name}") from exc

    def get_definition(self, name: str) -> ToolDefinition:
        return self.get_tool(name).definition

    def has_tool(self, name: str) -> bool:
        return name in self._native_tools

    def list_tools(self) -> list[NativeTool]:
        return list(self._native_tools.values())

    def list_definitions(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self.list_tools()]

    def list_model_schemas(self) -> list[dict]:
        return [definition.to_model_schema() for definition in self.list_definitions()]


def build_default_registry(*, include_write_tools: bool = False) -> ToolRegistry:
    return build_registry(include_write_tools=include_write_tools)


def build_registry(
    *,
    include_write_tools: bool = False,
    command_tool: NativeTool | None = None,
    command_tools: Iterable[NativeTool] | None = None,
) -> ToolRegistry:
    from app.tools.native.artifact_tools import (
        FinishTaskTool,
        ListArtifactsTool,
        WriteArtifactTool,
    )
    from app.tools.native.file_tools import (
        EditFileTool,
        ListFilesTool,
        ReadFileTool,
        WriteFileTool,
    )
    from app.tools.native.search_tools import SearchCodeTool

    registry = ToolRegistry()
    registry.register_many(
        [
            ListFilesTool(),
            ReadFileTool(),
            SearchCodeTool(),
            WriteArtifactTool(),
            ListArtifactsTool(),
            FinishTaskTool(),
        ]
    )
    if include_write_tools:
        registry.register_many([WriteFileTool(), EditFileTool()])
    if command_tool is not None:
        registry.register(command_tool)
    if command_tools is not None:
        registry.register_many(command_tools)
    return registry
