from __future__ import annotations

from app.llm.config import ModelSelection
from app.llm.providers.mock import MockProvider
from app.llm.registry import ModelRegistry
from app.llm.router import ModelRouter


def test_model_router_selects_registered_provider() -> None:
    registry = ModelRegistry()
    provider = MockProvider(provider_name="mock", model_name="mock-agent")
    registry.register(provider)

    selected = ModelRouter(registry).select(
        ModelSelection(provider="mock", model_name="mock-agent")
    )

    assert selected is provider
