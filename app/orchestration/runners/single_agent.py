from __future__ import annotations

from app.orchestration.agent_loop import AgentLoop, AgentLoopResult
from app.orchestration.runners.base import AgentRunner, RunnerInput
from app.tools.models import ToolContext


class SingleAgentRunner(AgentRunner):
    def __init__(self, agent_loop: AgentLoop) -> None:
        self.agent_loop = agent_loop

    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        model_name = runner_input.metadata.get("model_name")
        if not isinstance(model_name, str) or not model_name:
            model_name = None
        tool_context = ToolContext(
            task_id=runner_input.task_id,
            workspace_root=runner_input.workspace_root,
            artifact_root=runner_input.artifact_root,
            allow_write=runner_input.allow_write,
            role=runner_input.role,
            metadata=runner_input.metadata,
        )
        return await self.agent_loop.run(
            runner_input.task,
            tool_context,
            model_name=model_name,
        )
