from __future__ import annotations

from app.context.budget import ContextBudget
from app.context.models import CompactionLevel


class CompactionPolicy:
    def __init__(self, budget: ContextBudget | None = None) -> None:
        self.budget = budget or ContextBudget()

    def level_for(self, used_tokens: int) -> CompactionLevel:
        return self.budget.level_for(used_tokens)
