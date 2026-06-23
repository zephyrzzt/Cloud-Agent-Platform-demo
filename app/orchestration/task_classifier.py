from __future__ import annotations

from app.domain.task import TaskRequest, TaskType
from app.orchestration.execution_modes import (
    ExecutionMode,
    TaskComplexity,
    TaskPhase,
    TaskProfile,
)


class TaskClassifier:
    REPORT_KEYWORDS = {
        "report",
        "summary",
        "writeup",
        "status",
        "报告",
        "总结",
        "汇总",
    }
    COMPLEX_KEYWORDS = {
        "multi-agent",
        "sync",
        "parallel",
        "architecture",
        "system",
        "full-stack",
        "全量",
        "架构",
        "系统",
        "并行",
        "多 agent",
        "多agent",
        "多智能体",
    }
    MODERATE_KEYWORDS = {
        "fix",
        "implement",
        "test",
        "refactor",
        "review",
        "code",
        "coding",
        "build",
        "compile",
        "lint",
        "修复",
        "实现",
        "测试",
        "审查",
        "代码",
        "构建",
    }

    def classify(self, request: TaskRequest) -> TaskProfile:
        override = self._override_profile(request)
        if override is not None:
            return override

        text = request.prompt.lower()
        reasons: list[str] = []
        has_complex = any(keyword in text for keyword in self.COMPLEX_KEYWORDS)
        has_moderate = any(keyword in text for keyword in self.MODERATE_KEYWORDS)
        has_report = any(keyword in text for keyword in self.REPORT_KEYWORDS)

        if request.task_type == TaskType.REPORT or (has_report and not has_moderate):
            return TaskProfile(
                mode=ExecutionMode.SINGLE,
                complexity=TaskComplexity.SIMPLE,
                phases=[TaskPhase.REPORT],
                reasons=["report task"],
            )

        if has_complex:
            reasons.append("complex keyword")
            return TaskProfile(
                mode=ExecutionMode.SYNC,
                complexity=TaskComplexity.COMPLEX,
                phases=[TaskPhase.EXPLORE, TaskPhase.DEVELOP, TaskPhase.REVIEW],
                reasons=reasons,
            )

        if has_moderate or request.task_type == TaskType.CODING:
            reasons.append("coding or implementation task")
            return TaskProfile(
                mode=ExecutionMode.SEQUENTIAL,
                complexity=TaskComplexity.MODERATE,
                phases=[TaskPhase.EXPLORE, TaskPhase.DEVELOP, TaskPhase.REVIEW],
                reasons=reasons,
            )

        return TaskProfile(
            mode=ExecutionMode.SINGLE,
            complexity=TaskComplexity.SIMPLE,
            phases=[TaskPhase.EXPLORE],
            reasons=["simple analysis"],
        )

    def _override_profile(self, request: TaskRequest) -> TaskProfile | None:
        raw_mode = request.metadata.get("execution_mode")
        if not isinstance(raw_mode, str) or not raw_mode:
            return None

        mode = ExecutionMode(raw_mode.lower())
        if mode == ExecutionMode.SINGLE:
            phase = TaskPhase.REPORT if request.task_type == TaskType.REPORT else TaskPhase.EXPLORE
            phases = [phase]
            complexity = TaskComplexity.SIMPLE
        elif mode == ExecutionMode.SEQUENTIAL:
            phases = [TaskPhase.EXPLORE, TaskPhase.DEVELOP, TaskPhase.REVIEW]
            complexity = TaskComplexity.MODERATE
        else:
            phases = [TaskPhase.EXPLORE, TaskPhase.DEVELOP, TaskPhase.REVIEW]
            complexity = TaskComplexity.COMPLEX

        return TaskProfile(
            mode=mode,
            complexity=complexity,
            phases=phases,
            reasons=["metadata execution_mode override"],
        )
