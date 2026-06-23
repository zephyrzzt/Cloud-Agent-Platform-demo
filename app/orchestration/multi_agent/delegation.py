from __future__ import annotations

from app.orchestration.agent_loop import AgentLoopResult
from app.orchestration.multi_agent.models import DelegationRequest, DelegationResult
from app.orchestration.runners.base import AgentRunner, RunnerInput


class DelegationService:
    def __init__(self, runners: dict[str, AgentRunner]) -> None:
        self.runners = runners

    async def delegate(
        self,
        request: DelegationRequest,
        runner_input: RunnerInput,
    ) -> DelegationResult:
        runner = self.runners[request.role.value]
        result: AgentLoopResult = await runner.run(runner_input)
        return DelegationResult(
            request_id=request.id,
            role=request.role,
            phase=request.phase,
            success=result.completed,
            summary=result.final_response,
            metadata={
                "status": result.status,
                "turns": result.turns,
                "tool_calls": result.tool_calls,
            },
        )
