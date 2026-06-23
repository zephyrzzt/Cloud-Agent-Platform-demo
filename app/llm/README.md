# LLM Layer

This folder contains model-facing abstractions. First phase code includes:

- `models.py`: provider-neutral messages, requests, responses, tool calls, and usage data.
- `provider.py`: the common `ModelProvider` interface.
- `providers/mock.py`: a deterministic provider for tests and local agent-loop development.
- `providers/openai_compatible.py`: a `/chat/completions` adapter for OpenAI-compatible APIs.

The LLM layer only decides what should happen next. Actual actions must be returned as structured tool calls and executed by the tool pipeline.
