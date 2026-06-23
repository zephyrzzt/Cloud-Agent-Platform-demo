from __future__ import annotations

import json

import pytest

httpx = pytest.importorskip("httpx")

from app.llm.models import ChatMessage, ModelRequest, ModelToolCall
from app.llm.providers.openai_compatible import OpenAICompatibleProvider


def test_openai_compatible_provider_parses_text_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["messages"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            },
        )

    provider = _provider(handler)

    async def run():
        return await provider.generate(ModelRequest(messages=[ChatMessage.user("hi")]))

    import asyncio

    response = asyncio.run(run())
    assert response.content == "hello"
    assert response.usage.total_tokens == 5


def test_openai_compatible_provider_parses_tool_calls() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["tools"][0]["function"]["name"] == "finish_task"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "finish_task",
                                        "arguments": "{\"summary\":\"done\"}",
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            },
        )

    provider = _provider(handler)

    async def run():
        return await provider.generate(
            ModelRequest(
                messages=[ChatMessage.user("finish")],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "finish_task",
                            "description": "Finish",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            )
        )

    import asyncio

    response = asyncio.run(run())
    assert response.tool_calls == [
        ModelToolCall(id="call_1", name="finish_task", arguments={"summary": "done"})
    ]


def test_openai_compatible_serializes_assistant_tool_call_history() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            },
        )

    provider = _provider(handler)
    tool_call = ModelToolCall(
        id="call_1",
        name="read_file",
        arguments={"path": "README.md"},
    )

    async def run():
        return await provider.generate(
            ModelRequest(
                messages=[
                    ChatMessage.user("read"),
                    ChatMessage.assistant("", tool_calls=[tool_call]),
                    ChatMessage.tool("content", tool_call_id="call_1", name="read_file"),
                ]
            )
        )

    import asyncio

    asyncio.run(run())
    assistant_message = captured["messages"][1]
    assert assistant_message["tool_calls"][0]["id"] == "call_1"
    assert assistant_message["tool_calls"][0]["function"]["name"] == "read_file"


def _provider(handler) -> OpenAICompatibleProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return OpenAICompatibleProvider(
        model_name="test-model",
        base_url="https://example.test/v1",
        api_key="test-key",
        client=client,
    )
