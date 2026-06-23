from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")

from app.bootstrap.container import ConfigurableAgentRunner
from app.config.settings import Settings
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.registry import ModelRegistry
from app.llm.router import ModelRouter
from app.orchestration.runners.base import RunnerInput


def test_openai_compatible_runner_executes_tool_calls(tmp_path: Path) -> None:
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["model"] == "real-test-model"

        if len(requests) == 1:
            tool_names = {tool["function"]["name"] for tool in payload["tools"]}
            assert {"write_artifact", "finish_task"}.issubset(tool_names)
            assert payload["messages"][0]["role"] == "system"
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_write",
                                        "type": "function",
                                        "function": {
                                            "name": "write_artifact",
                                            "arguments": json.dumps(
                                                {
                                                    "path": "report.md",
                                                    "content": (
                                                        "# Real Provider Report\n\n"
                                                        "The real-model tool path works."
                                                    ),
                                                }
                                            ),
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                },
            )

        assert requests[-1]["messages"][-1]["role"] == "tool"
        assert requests[-1]["messages"][-1]["tool_call_id"] == "call_write"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_finish",
                                    "type": "function",
                                    "function": {
                                        "name": "finish_task",
                                        "arguments": json.dumps(
                                            {"summary": "real provider finished"}
                                        ),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    async def run_runner():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            registry = ModelRegistry()
            registry.register(
                OpenAICompatibleProvider(
                    model_name="fallback-model",
                    base_url="https://example.test/v1",
                    api_key="test-key",
                    client=client,
                )
            )
            runner = ConfigurableAgentRunner(
                settings=Settings(
                    default_model_provider="openai_compatible",
                    default_model_name="fallback-model",
                ),
                model_router=ModelRouter(registry),
                max_turns=4,
                max_tool_calls=4,
            )
            return await runner.run(
                RunnerInput(
                    task="Create a report artifact.",
                    task_id="task-real-model",
                    workspace_root=tmp_path / "workspace",
                    artifact_root=tmp_path / "artifacts",
                    metadata={
                        "model_provider": "openai_compatible",
                        "model_name": "real-test-model",
                    },
                )
            )
        finally:
            await client.aclose()

    result = asyncio.run(run_runner())

    assert result.status == "finished"
    assert result.final_response == "real provider finished"
    assert [item.tool_name for item in result.tool_results] == [
        "write_artifact",
        "finish_task",
    ]
    assert (tmp_path / "artifacts" / "report.md").read_text(
        encoding="utf-8"
    ).startswith("# Real Provider Report")
    assert len(requests) == 2
