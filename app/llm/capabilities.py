from __future__ import annotations

from enum import StrEnum


class ModelCapability(StrEnum):
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    VISION = "vision"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"
    PARALLEL_TOOL_CALLS = "parallel_tool_calls"
    PROMPT_CACHING = "prompt_caching"
