# Config

`Settings` centralizes runtime configuration for the API and bootstrap layer.

The current implementation reads from environment variables without requiring a database or secrets manager. Important values include:

- `WORKSPACE_ROOT`
- `DEFAULT_MODEL_PROVIDER`
- `DEFAULT_MODEL_NAME`
- `OPENAI_COMPATIBLE_BASE_URL`
- `OPENAI_COMPATIBLE_API_KEY`
- `OPENAI_COMPATIBLE_TIMEOUT_SECONDS`
- `TASK_WORKER_ENABLED`
- `TASK_WORKER_POLL_INTERVAL_SECONDS`
- `TASK_WORKER_LEASE_TTL_SECONDS`
- `TASK_WORKER_LEASE_HEARTBEAT_INTERVAL_SECONDS`
- `TASK_SCHEDULER_MAX_CONCURRENT_TASKS`
- `TASK_SCHEDULER_MAX_SANDBOX_TASKS`
- `AGENT_MAX_TURNS`
- `AGENT_MAX_TOOL_CALLS`
