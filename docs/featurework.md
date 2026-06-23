# Feature Work

This file tracks work intentionally left outside the current scoped MVP.

The current version focuses on four working areas:

- Agent orchestration and scheduling
- Sandbox and isolated execution
- LLM integration and tool calling
- Overall architecture and extensibility

The items below are useful next steps, but they are not required for the current GitHub-ready baseline.

## Agent Orchestration And Scheduling

- Persist task state, leases, lifecycle events, and worker state in a database.
- Add stronger recovery for interrupted tasks, orphaned containers, and expired leases.
- Make `SyncMultiAgentRunner` allocate a fresh blackboard per task so multi-agent state cannot leak across tasks.
- Add per-role model configuration, per-role tool permissions, and per-role context budgets.
- Expand the manager-style sync runner from fixed phases into dynamic delegation and phase rollback.
- Add task cancellation endpoints and cancellation-aware worker/orchestrator checks.

## Sandbox And Isolated Execution

- Replace Kubernetes and Firecracker placeholders with real providers.
- Implement true network allowlists instead of only disabled/default Docker networking.
- Add sandbox image selection based on repository language, required tools, and task profile.
- Add runtime capacity checks from the sandbox provider instead of only task-count limits.
- Add sandbox snapshot, file transfer, exposed-port, and debug-session capabilities.
- Add richer sandbox audit records for image, mounts, resource limits, commands, and cleanup.

## LLM Integration And Tool Calling

- Implement `model_catalog.py` for context windows, capabilities, costs, and default model choices.
- Implement `usage_tracker.py` for tokens, model calls, retries, latency, and per-agent usage.
- Extend `ModelRouter` to choose models by agent role, task complexity, required capabilities, context size, cost, and provider availability.
- Add provider fallback and model retry policy to the AgentLoop path.
- Wire streaming model responses into the API/WebSocket layer.
- Complete dedicated OpenAI, Anthropic, Google, and local/vLLM providers beyond the OpenAI-compatible adapter.
- Implement MCP client, manager, tool adapter, authentication boundary, and executor.
- Expand ToolPolicy for network permissions, sensitive files, remote writes, reviewer-debug grants, and risk-level gating.

## Context And Memory

- Connect `ContextManager` to `AgentLoop` so context lanes, compaction, file buffering, and recall affect actual model prompts.
- Add per-agent independent context lanes for Explorer, Developer, Reviewer, and Manager.
- Add light, medium, and heavy compaction selection based on token budgets and task phase.
- Persist context snapshots and recall indexes.

## Storage, Messaging, And Callbacks

- Replace `InMemoryTaskStore` with a persistent store.
- Make task lifecycle events append-only records instead of synthetic timestamp events.
- Connect `file_storage` providers to artifact storage.
- Finish pending-message storage, replay, ordering, and worker integration.
- Wire event callbacks to task lifecycle events with signing, retry, and delivery records.

## Observability And Operations

- Add structured logs for task lifecycle, model calls, tool calls, sandbox commands, verification, and callbacks.
- Add metrics for queue depth, active tasks, sandbox usage, model latency, tool latency, and failure rates.
- Add tracing across API, scheduler, worker, orchestrator, runner, model provider, tool executor, and sandbox provider.
- Add audit records for high-risk tool calls, sandbox commands, credentials, and MCP writes.
- Add production configuration examples for Docker, persistent storage, and deployment.

## Verification

- Parse controlled command outputs into structured test, lint, build, and compile evidence.
- Add task-type-specific verification profiles.
- Add semantic checks for reports, code changes, and repository state.
- Add richer failure categories and remediation hints.
