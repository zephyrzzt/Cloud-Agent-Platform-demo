from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.llm.capabilities import ModelCapability
from app.llm.models import (
    ChatMessage,
    ChatRole,
    FinishReason,
    ModelMetadata,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
    TokenUsage,
)
from app.llm.provider import ModelProvider, ModelProviderError


@dataclass
class OpenAICompatibleProvider(ModelProvider):
    model_name: str
    base_url: str
    api_key: str | None = None
    provider_name: str = "openai_compatible"
    timeout_seconds: float = 60.0
    client: httpx.AsyncClient | None = None

    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider=self.provider_name,
            model_name=self.model_name,
            capabilities={
                ModelCapability.TOOL_CALLING,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.STREAMING,
            },
        )

    def validate_config(self) -> None:
        if not self.base_url:
            raise ModelProviderError("OpenAI-compatible base_url is required")
        if not self.model_name:
            raise ModelProviderError("OpenAI-compatible model_name is required")

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.validate_config()
        payload = self._build_payload(request)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            response = await client.post(
                self._chat_completions_url(),
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except httpx.HTTPError as exc:
            raise ModelProviderError(f"OpenAI-compatible request failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

    def _chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _build_payload(self, request: ModelRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model or self.model_name,
            "messages": [self._message_to_wire(message) for message in request.messages],
        }
        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = "auto"
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        return payload

    def _message_to_wire(self, message: ChatMessage) -> dict[str, Any]:
        role = message.role.value if isinstance(message.role, ChatRole) else str(message.role)
        if role == ChatRole.TOOL.value:
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "name": message.name,
                "content": message.content,
            }

        item: dict[str, Any] = {
            "role": role,
            "content": message.content,
        }
        if role == ChatRole.ASSISTANT.value and message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(tool_call.arguments),
                    },
                }
                for tool_call in message.tool_calls
            ]
        return item

    def _parse_response(self, payload: dict[str, Any]) -> ModelResponse:
        choices = payload.get("choices") or []
        if not choices:
            raise ModelProviderError("OpenAI-compatible response has no choices")

        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls = [
            self._parse_tool_call(raw_tool_call)
            for raw_tool_call in message.get("tool_calls") or []
        ]
        finish_reason = self._finish_reason(choice.get("finish_reason"))
        usage = payload.get("usage") or {}

        if tool_calls:
            finish_reason = FinishReason.TOOL_CALLS

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("prompt_tokens_details", {}).get(
                    "cached_tokens",
                    0,
                )
                if isinstance(usage.get("prompt_tokens_details"), dict)
                else 0,
            ),
            raw=payload,
        )

    def _parse_tool_call(self, raw: dict[str, Any]) -> ModelToolCall:
        function = raw.get("function") or {}
        arguments_raw = function.get("arguments") or "{}"
        try:
            arguments = json.loads(arguments_raw)
        except json.JSONDecodeError:
            arguments = {"_raw": arguments_raw}
        kwargs = {
            "name": function.get("name") or "",
            "arguments": arguments,
        }
        if raw.get("id"):
            kwargs["id"] = raw["id"]
        return ModelToolCall(**kwargs)

    def _finish_reason(self, value: str | None) -> FinishReason | str:
        if value == "stop":
            return FinishReason.STOP
        if value == "length":
            return FinishReason.LENGTH
        if value == "tool_calls":
            return FinishReason.TOOL_CALLS
        return value or FinishReason.STOP
