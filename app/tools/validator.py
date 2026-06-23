from __future__ import annotations

from typing import Any

from app.tools.models import ToolDefinition, ToolRequest


class ToolValidationError(ValueError):
    pass


class ToolValidator:
    def validate_request(
        self,
        request: ToolRequest,
        definition: ToolDefinition,
    ) -> None:
        if request.tool_name != definition.name:
            raise ToolValidationError(
                f"Tool request name {request.tool_name!r} does not match "
                f"definition {definition.name!r}"
            )
        self.validate_arguments(request.arguments, definition.parameters_schema)

    def validate_arguments(
        self,
        arguments: dict[str, Any],
        schema: dict[str, Any] | None,
    ) -> None:
        schema = schema or {"type": "object", "properties": {}}
        if schema.get("type", "object") != "object":
            raise ToolValidationError("Tool parameter schema must be an object")

        required = schema.get("required", [])
        for key in required:
            if key not in arguments:
                raise ToolValidationError(f"Missing required argument: {key}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = set(arguments) - set(properties)
            if unknown:
                raise ToolValidationError(
                    f"Unknown argument(s): {', '.join(sorted(unknown))}"
                )

        for key, value in arguments.items():
            expected_schema = properties.get(key)
            if expected_schema is None:
                continue
            self._validate_value(key, value, expected_schema)

    def _validate_value(
        self,
        key: str,
        value: Any,
        schema: dict[str, Any],
    ) -> None:
        expected_type = schema.get("type")
        if expected_type is None:
            return

        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            return

        if expected_type == "integer" and isinstance(value, bool):
            raise ToolValidationError(f"Argument {key!r} must be an integer")

        if expected_type == "number" and isinstance(value, bool):
            raise ToolValidationError(f"Argument {key!r} must be a number")

        if not isinstance(value, expected_python_type):
            raise ToolValidationError(
                f"Argument {key!r} must be {expected_type}, got "
                f"{type(value).__name__}"
            )
