from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tools.models import PolicyDecision, ToolContext, ToolDefinition, ToolRequest


PATH_ARGUMENT_NAMES = {
    "path",
    "file",
    "file_path",
    "directory",
    "directory_path",
    "working_directory",
    "output_path",
}


class ToolPolicy:
    def evaluate(
        self,
        request: ToolRequest,
        definition: ToolDefinition,
        context: ToolContext,
    ) -> PolicyDecision:
        if definition.requires_write and not context.allow_write:
            return PolicyDecision.deny(
                f"Tool {definition.name} requires write permission"
            )

        if definition.allowed_roles and context.role not in definition.allowed_roles:
            return PolicyDecision.deny(
                f"Role {context.role!r} cannot use tool {definition.name}"
            )

        for raw_path in self._extract_path_arguments(request.arguments):
            decision = self._check_path(raw_path, context)
            if not decision.allowed:
                return decision

        return PolicyDecision.allow()

    def _extract_path_arguments(self, value: Any) -> list[str]:
        paths: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = key.lower()
                if isinstance(item, str) and normalized_key in PATH_ARGUMENT_NAMES:
                    paths.append(item)
                else:
                    paths.extend(self._extract_path_arguments(item))
        elif isinstance(value, list):
            for item in value:
                paths.extend(self._extract_path_arguments(item))
        return paths

    def _check_path(self, raw_path: str, context: ToolContext) -> PolicyDecision:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = context.workspace_path() / candidate
        resolved = candidate.resolve()

        for root in context.allowed_roots():
            try:
                resolved.relative_to(root)
                return PolicyDecision.allow()
            except ValueError:
                continue

        return PolicyDecision.deny(
            f"Path {raw_path!r} is outside the allowed workspace"
        )
