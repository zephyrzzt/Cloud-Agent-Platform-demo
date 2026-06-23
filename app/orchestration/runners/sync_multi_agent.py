from __future__ import annotations

from app.orchestration.agent_loop import AgentLoopResult
from app.orchestration.execution_modes import TaskPhase
from app.orchestration.multi_agent.blackboard import Blackboard
from app.orchestration.multi_agent.coordinator import MultiAgentCoordinator
from app.orchestration.multi_agent.roles import AgentRole
from app.orchestration.runners.base import AgentRunner, RunnerInput


class SyncMultiAgentRunner(AgentRunner):
    def __init__(
        self,
        runners: dict[AgentRole, AgentRunner],
        *,
        phases: list[TaskPhase] | None = None,
        blackboard: Blackboard | None = None,
    ) -> None:
        self.blackboard = blackboard or Blackboard()
        self.phases = phases or [TaskPhase.EXPLORE, TaskPhase.DEVELOP, TaskPhase.REVIEW]
        self.coordinator = MultiAgentCoordinator(
            blackboard=self.blackboard,
            runners=runners,
        )

    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        return await self.coordinator.run_phases(runner_input, self.phases)
