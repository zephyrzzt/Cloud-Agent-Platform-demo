from __future__ import annotations

import asyncio

from app.llm.providers.mock import MockProvider
from app.orchestration.agent_loop import AgentLoop, AgentLoopConfig
from app.orchestration.runners.base import RunnerInput
from app.orchestration.runners.single_agent import SingleAgentRunner
from app.tools.executors.native_executor import NativeExecutor
from app.tools.models import ToolContext, ToolRequest
from app.tools.registry import build_default_registry


def test_mock_provider_returns_scripted_text() -> None:
    provider = MockProvider.from_responses(["done"])

    async def run() -> str:
        response = await provider.generate(request=_empty_request())
        return response.content

    assert asyncio.run(run()) == "done"


def test_native_executor_reads_workspace_file(tmp_path) -> None:
    (tmp_path / "hello.txt").write_text("hello platform", encoding="utf-8")
    registry = build_default_registry()
    executor = NativeExecutor(registry)
    context = ToolContext(task_id="t1", workspace_root=tmp_path)
    request = ToolRequest(tool_name="read_file", arguments={"path": "hello.txt"})

    result = asyncio.run(executor.execute(request, context))

    assert result.success is True
    assert result.content == "hello platform"


def test_native_executor_denies_path_escape(tmp_path) -> None:
    registry = build_default_registry()
    executor = NativeExecutor(registry)
    context = ToolContext(task_id="t1", workspace_root=tmp_path)
    request = ToolRequest(tool_name="read_file", arguments={"path": "../secret.txt"})

    result = asyncio.run(executor.execute(request, context))

    assert result.success is False
    assert "outside the allowed workspace" in result.content


def test_agent_loop_executes_tool_call_and_finishes(tmp_path) -> None:
    (tmp_path / "notes.txt").write_text("phase one", encoding="utf-8")
    provider = MockProvider.from_responses(
        [
            {
                "tool_calls": [
                    {
                        "name": "read_file",
                        "arguments": {"path": "notes.txt"},
                    }
                ]
            },
            {
                "tool_calls": [
                    {
                        "name": "finish_task",
                        "arguments": {"summary": "Read notes.txt successfully."},
                    }
                ]
            },
        ]
    )
    registry = build_default_registry()
    executor = NativeExecutor(registry)
    loop = AgentLoop(
        model_provider=provider,
        tool_registry=registry,
        tool_executor=executor,
        config=AgentLoopConfig(max_turns=4, max_tool_calls=4),
    )
    context = ToolContext(task_id="t1", workspace_root=tmp_path)

    result = asyncio.run(loop.run("Read notes.txt", context))

    assert result.status == "finished"
    assert result.final_response == "Read notes.txt successfully."
    assert [tool.tool_name for tool in result.tool_results] == [
        "read_file",
        "finish_task",
    ]


def test_single_agent_runner_wraps_agent_loop(tmp_path) -> None:
    provider = MockProvider.from_responses(["plain final answer"])
    registry = build_default_registry()
    executor = NativeExecutor(registry)
    loop = AgentLoop(provider, registry, executor)
    runner = SingleAgentRunner(loop)

    result = asyncio.run(
        runner.run(RunnerInput(task="Say hello", workspace_root=tmp_path))
    )

    assert result.completed is True
    assert result.final_response == "plain final answer"


def _empty_request():
    from app.llm.models import ModelRequest

    return ModelRequest(messages=[])
