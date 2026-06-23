from __future__ import annotations

from dataclasses import dataclass

from app.context.models import CompactionLevel


@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int = 8_000
    light_threshold: float = 0.5
    medium_threshold: float = 0.75
    heavy_threshold: float = 0.9

    def level_for(self, used_tokens: int) -> CompactionLevel:
        ratio = used_tokens / max(1, self.max_tokens)
        if ratio >= self.heavy_threshold:
            return CompactionLevel.HEAVY
        if ratio >= self.medium_threshold:
            return CompactionLevel.MEDIUM
        if ratio >= self.light_threshold:
            return CompactionLevel.LIGHT
        return CompactionLevel.NORMAL
