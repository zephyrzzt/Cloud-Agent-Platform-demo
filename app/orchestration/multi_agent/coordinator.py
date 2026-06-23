from __future__ import annotations

from app.orchestration.agent_loop import AgentLoopResult
from app.orchestration.execution_modes import TaskPhase
from app.orchestration.multi_agent.blackboard import Blackboard
from app.orchestration.multi_agent.models import DelegationRequest, DelegationResult
from app.orchestration.multi_agent.roles import AgentRole
from app.orchestration.runners.base import AgentRunner, RunnerInput


PHASE_ROLE_MAP = {
    TaskPhase.EXPLORE: AgentRole.EXPLORER,
    TaskPhase.DEVELOP: AgentRole.DEVELOPER,
    TaskPhase.REVIEW: AgentRole.REVIEWER,
    TaskPhase.REPORT: AgentRole.MANAGER,
}


class MultiAgentCoordinator:
    def __init__(
        self,
        *,
        blackboard: Blackboard,
        runners: dict[AgentRole, AgentRunner],
    ) -> None:
        self.blackboard = blackboard
        self.runners = runners

    async def run_phases(
        self,
        runner_input: RunnerInput,
        phases: list[TaskPhase],
    ) -> AgentLoopResult:
        summaries: list[str] = []
        total_turns = 0
        total_tool_calls = 0
        for phase in phases:
            role = PHASE_ROLE_MAP[phase]
            request = DelegationRequest(
                task_id=runner_input.task_id,
                phase=phase,
                role=role,
                prompt=runner_input.task,
                context=self.blackboard.snapshot(),
            )
            result = await self._run_delegate(request, runner_input)
            prefix = self._blackboard_prefix(role)
            self.blackboard.write(
                f"{prefix}:{phase.value}",
                {
                    "success": result.success,
                    "summary": result.summary,
                    "metadata": result.metadata,
                },
                role,
            )
            total_turns += int(result.metadata.get("turns", 0))
            total_tool_calls += int(result.metadata.get("tool_calls", 0))
            summaries.append(f"{role.value}/{phase.value}: {result.summary}")
            if not result.success:
                return AgentLoopResult(
                    status="delegation_failed",
                    final_response=result.summary,
                    messages=[],
                    turns=total_turns,
                    tool_calls=total_tool_calls,
                )

        return AgentLoopResult(
            status="completed",
            final_response="\n".join(summaries),
            messages=[],
            turns=total_turns,
            tool_calls=total_tool_calls,
        )

    async def _run_delegate(
        self,
        request: DelegationRequest,
        runner_input: RunnerInput,
    ) -> DelegationResult:
        runner = self.runners[request.role]
        result = await runner.run(
            RunnerInput(
                task=(
                    f"Role: {request.role.value}\n"
                    f"Phase: {request.phase.value}\n"
                    f"Task: {request.prompt}\n"
                    f"Blackboard: {request.context}"
                ),
                task_id=runner_input.task_id,
                workspace_root=runner_input.workspace_root,
                artifact_root=runner_input.artifact_root,
                allow_write=runner_input.allow_write,
                role=request.role.value,
                metadata={**runner_input.metadata, "phase": request.phase.value},
            )
        )
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

    def _blackboard_prefix(self, role: AgentRole) -> str:
        if role == AgentRole.EXPLORER:
            return "finding"
        if role == AgentRole.DEVELOPER:
            return "implementation"
        if role == AgentRole.REVIEWER:
            return "review"
        return "decision"
