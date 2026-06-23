from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.sandbox.errors import SandboxError
from app.sandbox.models import CommandSpec
from app.sandbox.service import SandboxService
from app.tools.base import NativeTool
from app.tools.models import (
    ToolContext,
    ToolDefinition,
    ToolRequest,
    ToolResult,
    ToolRiskLevel,
)


CONTROLLED_COMMAND_TOOLS = {
    "run_test",
    "run_lint",
    "run_build",
    "run_compile",
    "run_program",
}


def build_controlled_command_tools(
    *,
    sandbox_service: SandboxService,
    sandbox_id: str,
    default_timeout_seconds: int = 30,
    default_max_output_bytes: int = 20_000,
) -> list[NativeTool]:
    kwargs = {
        "sandbox_service": sandbox_service,
        "sandbox_id": sandbox_id,
        "default_timeout_seconds": default_timeout_seconds,
        "default_max_output_bytes": default_max_output_bytes,
    }
    return [
        RunTestTool(**kwargs),
        RunLintTool(**kwargs),
        RunBuildTool(**kwargs),
        RunCompileTool(**kwargs),
        RunProgramTool(**kwargs),
    ]


@dataclass
class ControlledCommandTool(NativeTool):
    sandbox_service: SandboxService
    sandbox_id: str
    default_timeout_seconds: int = 30
    default_max_output_bytes: int = 20_000

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,
    ) -> ToolResult:
        context.artifact_path().mkdir(parents=True, exist_ok=True)
        try:
            command_spec = self.command_spec(request.arguments)
            command_result = await self.sandbox_service.execute(
                self.sandbox_id,
                command_spec,
            )
        except (SandboxError, ValueError) as exc:
            return ToolResult.failed(request, str(exc))

        content = self._format_output(command_result.stdout, command_result.stderr)
        data = {
            **command_result.model_dump(),
            "controlled_tool": request.tool_name,
        }
        if command_result.success:
            return ToolResult.ok(request, content, data=data)

        return ToolResult(
            tool_name=request.tool_name,
            request_id=request.id,
            success=False,
            content=content,
            data=data,
            error=(
                "Command timed out"
                if command_result.timed_out
                else f"Command exited with {command_result.exit_code}"
            ),
        )

    def command_spec(self, arguments: dict[str, Any]) -> CommandSpec:
        argv = self.build_argv(arguments)
        return CommandSpec(
            argv=argv,
            working_directory="/workspace/repository",
            timeout_seconds=self._timeout(arguments),
            max_output_bytes=self._max_output_bytes(arguments),
        )

    def build_argv(self, arguments: dict[str, Any]) -> list[str]:
        raise NotImplementedError

    def _timeout(self, arguments: dict[str, Any]) -> int:
        value = arguments.get("timeout_seconds", self.default_timeout_seconds)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("timeout_seconds must be a positive integer")
        return value

    def _max_output_bytes(self, arguments: dict[str, Any]) -> int:
        value = arguments.get("max_output_bytes", self.default_max_output_bytes)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("max_output_bytes must be a positive integer")
        return value

    def _path(self, arguments: dict[str, Any], *, default: str = ".") -> str:
        value = arguments.get("path", default)
        if not isinstance(value, str) or not value:
            raise ValueError("path must be a non-empty string")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("path must stay inside the repository")
        return path.as_posix()

    def _string_arg(
        self,
        arguments: dict[str, Any],
        name: str,
        *,
        default: str | None = None,
    ) -> str:
        value = arguments.get(name, default)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
        return value

    def _extra_args(self, arguments: dict[str, Any], *, name: str = "args") -> list[str]:
        value = arguments.get(name, [])
        if not isinstance(value, list):
            raise ValueError(f"{name} must be an array")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item:
                raise ValueError(f"{name} must contain non-empty strings")
            items.append(item)
        return items

    def _format_output(self, stdout: str, stderr: str) -> str:
        parts: list[str] = []
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        return "\n\n".join(parts) if parts else "(no output)"


class RunTestTool(ControlledCommandTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_test",
            description="Run a supported test command in the task sandbox.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "path": {"type": "string"},
                    "args": {"type": "array"},
                    "timeout_seconds": {"type": "integer"},
                    "max_output_bytes": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            risk_level=ToolRiskLevel.HIGH,
        )

    def build_argv(self, arguments: dict[str, Any]) -> list[str]:
        tool = self._string_arg(arguments, "tool", default="pytest")
        path = self._path(arguments)
        extra_args = self._extra_args(arguments)
        if tool == "pytest":
            return ["python", "-m", "pytest", path, *extra_args]
        if tool == "unittest":
            return ["python", "-m", "unittest", "discover", "-s", path, *extra_args]
        if tool == "npm":
            return ["npm", "test", "--", *extra_args]
        raise ValueError("Unsupported test tool")


class RunLintTool(ControlledCommandTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_lint",
            description="Run a supported lint command in the task sandbox.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "path": {"type": "string"},
                    "args": {"type": "array"},
                    "timeout_seconds": {"type": "integer"},
                    "max_output_bytes": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            risk_level=ToolRiskLevel.HIGH,
        )

    def build_argv(self, arguments: dict[str, Any]) -> list[str]:
        tool = self._string_arg(arguments, "tool", default="ruff")
        path = self._path(arguments)
        extra_args = self._extra_args(arguments)
        if tool == "ruff":
            return ["python", "-m", "ruff", "check", path, *extra_args]
        if tool == "flake8":
            return ["python", "-m", "flake8", path, *extra_args]
        if tool == "npm":
            return ["npm", "run", "lint", "--", *extra_args]
        raise ValueError("Unsupported lint tool")


class RunBuildTool(ControlledCommandTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_build",
            description="Run a supported project build command in the task sandbox.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "target": {"type": "string"},
                    "args": {"type": "array"},
                    "timeout_seconds": {"type": "integer"},
                    "max_output_bytes": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            risk_level=ToolRiskLevel.HIGH,
        )

    def build_argv(self, arguments: dict[str, Any]) -> list[str]:
        tool = self._string_arg(arguments, "tool", default="python")
        target = arguments.get("target")
        extra_args = self._extra_args(arguments)
        if target is not None and (not isinstance(target, str) or not target):
            raise ValueError("target must be a non-empty string")
        if tool == "python":
            argv = ["python", "-m", "build"]
            if target:
                argv.append(self._path({"path": target}))
            return [*argv, *extra_args]
        if tool == "npm":
            return ["npm", "run", "build", "--", *extra_args]
        if tool == "make":
            return ["make", *( [target] if target else [] ), *extra_args]
        raise ValueError("Unsupported build tool")


class RunCompileTool(ControlledCommandTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_compile",
            description="Run a supported compile or static check command in the task sandbox.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "path": {"type": "string"},
                    "args": {"type": "array"},
                    "timeout_seconds": {"type": "integer"},
                    "max_output_bytes": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            risk_level=ToolRiskLevel.HIGH,
        )

    def build_argv(self, arguments: dict[str, Any]) -> list[str]:
        language = self._string_arg(arguments, "language", default="python")
        path = self._path(arguments)
        extra_args = self._extra_args(arguments)
        if language == "python":
            return ["python", "-m", "compileall", path, *extra_args]
        if language == "go":
            return ["go", "test", "./...", *extra_args]
        if language == "rust":
            return ["cargo", "check", *extra_args]
        if language == "typescript":
            return ["npm", "run", "typecheck", "--", *extra_args]
        raise ValueError("Unsupported compile language")


class RunProgramTool(ControlledCommandTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_program",
            description="Run a repository program through a supported runtime.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "runtime": {"type": "string"},
                    "path": {"type": "string"},
                    "module": {"type": "string"},
                    "args": {"type": "array"},
                    "timeout_seconds": {"type": "integer"},
                    "max_output_bytes": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            risk_level=ToolRiskLevel.HIGH,
        )

    def build_argv(self, arguments: dict[str, Any]) -> list[str]:
        runtime = self._string_arg(arguments, "runtime", default="python")
        extra_args = self._extra_args(arguments)
        if runtime == "python":
            module = arguments.get("module")
            if module is not None:
                if not isinstance(module, str) or not module:
                    raise ValueError("module must be a non-empty string")
                return ["python", "-m", module, *extra_args]
            path = self._path(arguments)
            return ["python", path, *extra_args]
        if runtime == "node":
            path = self._path(arguments)
            return ["node", path, *extra_args]
        raise ValueError("Unsupported program runtime")
