from __future__ import annotations

from app.llm.provider import ModelProvider


class ModelRegistryError(RuntimeError):
    pass


class ModelProviderNotFoundError(ModelRegistryError):
    pass


class ModelRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider, *, replace: bool = False) -> None:
        name = provider.metadata.provider
        if name in self._providers and not replace:
            raise ModelRegistryError(f"Model provider already registered: {name}")
        self._providers[name] = provider

    def get(self, provider_name: str) -> ModelProvider:
        try:
            return self._providers[provider_name]
        except KeyError as exc:
            raise ModelProviderNotFoundError(
                f"Model provider not found: {provider_name}"
            ) from exc

    def has(self, provider_name: str) -> bool:
        return provider_name in self._providers

    def list(self) -> list[ModelProvider]:
        return list(self._providers.values())
