from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.llm.capabilities import ModelCapability
from app.llm.models import (
    ChatMessage,
    ChatRole,
    ModelMetadata,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from app.llm.provider import ModelProvider


ScriptedResponse = ModelResponse | str | dict[str, Any]


@dataclass
class MockProvider(ModelProvider):
    responses: list[ScriptedResponse] = field(default_factory=list)
    provider_name: str = "mock"
    model_name: str = "mock-agent"

    @classmethod
    def from_responses(cls, responses: Iterable[ScriptedResponse]) -> "MockProvider":
        return cls(responses=list(responses))

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider=self.provider_name,
            model_name=self.model_name,
            context_window=128_000,
            max_output_tokens=8_192,
            capabilities={
                ModelCapability.TOOL_CALLING,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.STREAMING,
            },
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if self.responses:
            return self._coerce_response(self.responses.pop(0))

        last_user_message = self._last_user_message(request.messages)
        if last_user_message is None:
            return ModelResponse.text("Mock response.")

        return ModelResponse.text(f"Mock response: {last_user_message.content}")

    def _coerce_response(self, response: ScriptedResponse) -> ModelResponse:
        if isinstance(response, ModelResponse):
            return response

        if isinstance(response, str):
            return ModelResponse.text(response)

        tool_calls = []
        for item in response.get("tool_calls", []):
            kwargs = {
                "name": item["name"],
                "arguments": item.get("arguments", {}),
            }
            tool_call_id = item.get("id") or item.get("tool_call_id")
            if tool_call_id:
                kwargs["id"] = tool_call_id
            tool_calls.append(ModelToolCall(**kwargs))
        if tool_calls:
            return ModelResponse.tools(
                tool_calls=tool_calls,
                content=response.get("content", ""),
            )

        return ModelResponse.text(response.get("content", ""))

    def _last_user_message(self, messages: list[ChatMessage]) -> ChatMessage | None:
        for message in reversed(messages):
            if message.role == ChatRole.USER:
                return message
        return None
