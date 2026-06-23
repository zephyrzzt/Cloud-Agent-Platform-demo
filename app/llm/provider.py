from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.llm.models import ModelMetadata, ModelRequest, ModelResponse


class ModelProviderError(RuntimeError):
    pass


class ModelProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ModelMetadata:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelResponse]:
        yield await self.generate(request)

    def supports(self, capability: str) -> bool:
        return capability in self.metadata.capabilities

    def validate_config(self) -> None:
        return None
