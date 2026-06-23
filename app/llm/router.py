from __future__ import annotations

from app.llm.config import ModelSelection
from app.llm.provider import ModelProvider
from app.llm.registry import ModelRegistry


class ModelRouter:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def select(self, selection: ModelSelection) -> ModelProvider:
        return self.registry.get(selection.provider)
