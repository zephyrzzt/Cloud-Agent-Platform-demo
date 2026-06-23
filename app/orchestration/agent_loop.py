from __future__ import annotations

from dataclasses import dataclass, field

from app.llm.models import ChatMessage, ModelRequest, ModelResponse
from app.llm.provider import ModelProvider
from app.tools.executors.base import ToolExecutor
from app.tools.models import ToolContext, ToolRequest, ToolResult
from app.tools.registry import ToolRegistry


@dataclass(frozen=True)
class AgentLoopConfig:
    max_turns: int = 8
    max_tool_calls: int = 24
    system_prompt: str = (
        "You are a repository task agent. Use the available tools for durable "
        "side effects. When the task asks for a report, summary, or generated "
        "result, write it with write_artifact before finishing. Call finish_task "
        "only after the needed artifact or result has been produced. For sandbox "
        "commands, use the controlled tools run_test, run_lint, run_build, "
        "run_compile, or run_program."
    )


@dataclass(frozen=True)
class AgentLoopResult:
    status: str
    final_response: str
    messages: list[ChatMessage]
    model_responses: list[ModelResponse] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    turns: int = 0
    tool_calls: int = 0

    @property
    def completed(self) -> bool:
        return self.status in {"completed", "finished"}


class AgentLoop:
    def __init__(
        self,
        model_provider: ModelProvider,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        config: AgentLoopConfig | None = None,
    ) -> None:
        self.model_provider = model_provider
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.config = config or AgentLoopConfig()

    async def run(
        self,
        task: str,
        tool_context: ToolContext,
        *,
        initial_messages: list[ChatMessage] | None = None,
        system_prompt: str | None = None,
        model_name: str | None = None,
    ) -> AgentLoopResult:
        messages = list(initial_messages or [])
        if not messages:
            messages.append(
                ChatMessage.system(system_prompt or self.config.system_prompt)
            )
            messages.append(ChatMessage.user(task))

        model_responses: list[ModelResponse] = []
        tool_results: list[ToolResult] = []
        total_tool_calls = 0

        for turn in range(1, self.config.max_turns + 1):
            response = await self.model_provider.generate(
                ModelRequest(
                    messages=messages,
                    tools=self.tool_registry.list_model_schemas(),
                    model=model_name,
                )
            )
            model_responses.append(response)

            if response.content or response.tool_calls:
                messages.append(
                    ChatMessage.assistant(
                        response.content,
                        tool_calls=response.tool_calls,
                    )
                )

            if not response.tool_calls:
                return AgentLoopResult(
                    status="completed",
                    final_response=response.content,
                    messages=messages,
                    model_responses=model_responses,
                    tool_results=tool_results,
                    turns=turn,
                    tool_calls=total_tool_calls,
                )

            for tool_call in response.tool_calls:
                if total_tool_calls >= self.config.max_tool_calls:
                    return AgentLoopResult(
                        status="tool_limit_reached",
                        final_response="Tool call limit reached.",
                        messages=messages,
                        model_responses=model_responses,
                        tool_results=tool_results,
                        turns=turn,
                        tool_calls=total_tool_calls,
                    )

                request = ToolRequest(
                    id=tool_call.id,
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                )
                result = await self.tool_executor.execute(request, tool_context)
                tool_results.append(result)
                total_tool_calls += 1

                messages.append(
                    ChatMessage.tool(
                        content=result.to_model_content(),
                        tool_call_id=tool_call.id,
                        name=tool_call.name,
                    )
                )

                if (
                    tool_call.name == "finish_task"
                    and result.success
                    and isinstance(result.data, dict)
                    and result.data.get("finished") is True
                ):
                    return AgentLoopResult(
                        status="finished",
                        final_response=result.content,
                        messages=messages,
                        model_responses=model_responses,
                        tool_results=tool_results,
                        turns=turn,
                        tool_calls=total_tool_calls,
                    )

        return AgentLoopResult(
            status="turn_limit_reached",
            final_response="Turn limit reached.",
            messages=messages,
            model_responses=model_responses,
            tool_results=tool_results,
            turns=self.config.max_turns,
            tool_calls=total_tool_calls,
        )
