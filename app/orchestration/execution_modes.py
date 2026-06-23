from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExecutionMode(StrEnum):
    SINGLE = "single"
    SEQUENTIAL = "sequential"
    SYNC = "sync"


class TaskPhase(StrEnum):
    EXPLORE = "explore"
    DEVELOP = "develop"
    REVIEW = "review"
    REPORT = "report"


class TaskComplexity(StrEnum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass(frozen=True)
class TaskProfile:
    mode: ExecutionMode
    complexity: TaskComplexity
    phases: list[TaskPhase]
    reasons: list[str] = field(default_factory=list)
