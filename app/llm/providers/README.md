# Model Providers

Provider modules adapt concrete model vendors to the platform-level `ModelProvider` interface.

The provider package includes:

- `MockProvider`: scripted text or tool-call responses without any external network dependency.
- `OpenAICompatibleProvider`: a lightweight HTTP adapter for `/chat/completions` APIs that support OpenAI-style messages and tools.

The OpenAI-compatible adapter sends platform tool schemas with `tool_choice=auto`, preserves assistant tool-call history, reads tool results back as `tool` messages, and parses returned tool calls into the platform `ModelToolCall` model. In the default agent loop, a real model can save task output with `write_artifact` and complete the task with `finish_task`.

To use an OpenAI-compatible provider, set:

```bash
DEFAULT_MODEL_PROVIDER=openai_compatible
DEFAULT_MODEL_NAME=your-model
OPENAI_COMPATIBLE_BASE_URL=https://api.openai.com/v1
OPENAI_COMPATIBLE_API_KEY=your-key
```
