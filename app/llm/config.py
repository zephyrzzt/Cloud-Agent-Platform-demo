from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model_name: str
    temperature: float | None = None
    max_output_tokens: int | None = None


@dataclass(frozen=True)
class ModelSelection:
    provider: str
    model_name: str


@dataclass(frozen=True)
class FallbackConfig:
    selections: list[ModelSelection] = field(default_factory=list)
