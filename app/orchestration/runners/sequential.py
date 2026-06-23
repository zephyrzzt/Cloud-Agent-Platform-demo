from __future__ import annotations

from dataclasses import dataclass

from app.llm.models import ChatMessage
from app.orchestration.agent_loop import AgentLoopResult
from app.orchestration.execution_modes import TaskPhase
from app.orchestration.runners.base import AgentRunner, RunnerInput


@dataclass(frozen=True)
class PhaseRunner:
    phase: TaskPhase
    runner: AgentRunner


class SequentialRunner(AgentRunner):
    def __init__(self, phase_runners: list[PhaseRunner]) -> None:
        if not phase_runners:
            raise ValueError("SequentialRunner requires at least one phase runner")
        self.phase_runners = phase_runners

    async def run(self, runner_input: RunnerInput) -> AgentLoopResult:
        summaries: list[str] = []
        messages: list[ChatMessage] = []
        total_turns = 0
        total_tool_calls = 0

        for phase_runner in self.phase_runners:
            phase_input = RunnerInput(
                task=self._phase_prompt(runner_input.task, phase_runner.phase, summaries),
                task_id=runner_input.task_id,
                workspace_root=runner_input.workspace_root,
                artifact_root=runner_input.artifact_root,
                allow_write=runner_input.allow_write,
                role=phase_runner.phase.value,
                metadata={
                    **runner_input.metadata,
                    "phase": phase_runner.phase.value,
                    "previous_summaries": list(summaries),
                },
            )
            result = await phase_runner.runner.run(phase_input)
            messages.extend(result.messages)
            total_turns += result.turns
            total_tool_calls += result.tool_calls
            summaries.append(f"{phase_runner.phase.value}: {result.final_response}")

            if not result.completed:
                return AgentLoopResult(
                    status=result.status,
                    final_response=result.final_response,
                    messages=messages,
                    turns=total_turns,
                    tool_calls=total_tool_calls,
                )

        return AgentLoopResult(
            status="completed",
            final_response="\n".join(summaries),
            messages=messages,
            turns=total_turns,
            tool_calls=total_tool_calls,
        )

    def _phase_prompt(
        self,
        task: str,
        phase: TaskPhase,
        previous_summaries: list[str],
    ) -> str:
        context = "\n".join(previous_summaries)
        if context:
            return f"Phase: {phase.value}\nTask: {task}\nPrevious phase summaries:\n{context}"
        return f"Phase: {phase.value}\nTask: {task}"
