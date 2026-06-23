from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ChatRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    ERROR = "error"


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole | str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list["ModelToolCall"] = field(default_factory=list)

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role=ChatRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role=ChatRole.USER, content=content)

    @classmethod
    def assistant(
        cls,
        content: str,
        tool_calls: list["ModelToolCall"] | None = None,
    ) -> "ChatMessage":
        return cls(
            role=ChatRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
        )

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str) -> "ChatMessage":
        return cls(
            role=ChatRole.TOOL,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
        )


@dataclass(frozen=True)
class ModelToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"tool_{uuid4().hex}")


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ModelMetadata:
    provider: str
    model_name: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ModelRequest:
    messages: list[ChatMessage]
    tools: list[dict[str, Any]] = field(default_factory=list)
    model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    content: str = ""
    tool_calls: list[ModelToolCall] = field(default_factory=list)
    finish_reason: FinishReason | str = FinishReason.STOP
    usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None

    @classmethod
    def text(cls, content: str) -> "ModelResponse":
        return cls(content=content, finish_reason=FinishReason.STOP)

    @classmethod
    def tools(
        cls,
        tool_calls: list[ModelToolCall],
        content: str = "",
    ) -> "ModelResponse":
        return cls(
            content=content,
            tool_calls=tool_calls,
            finish_reason=FinishReason.TOOL_CALLS,
        )
