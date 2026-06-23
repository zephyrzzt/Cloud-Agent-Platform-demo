# Orchestration

Orchestration owns task execution flow above the model and tool layers.

Phase one implements the smallest useful loop:

1. Send task context and available tool schemas to a model provider.
2. Receive text or structured tool calls.
3. Execute tool calls through the tool pipeline.
4. Feed tool results back into the model.
5. Stop when the model returns final text, calls `finish_task`, or hits limits.

Phase three adds the first task lifecycle pipeline:

- `TaskScheduler` accepts task requests and queues tasks.
- `ExecutionLeaseManager` prevents two workers from processing the same task.
- `TaskStateMachine` enforces legal task transitions.
- `TaskWorker` claims queued work, heartbeats its lease during long tasks, and delegates execution.
- `TaskOrchestrator` prepares workspace state, calls the configured runner, and records results.

`TaskScheduler` uses priority-aware selection rather than plain FIFO. Higher `TaskRequest.priority` values run first, while `max_concurrent_tasks` and `max_sandbox_tasks` can prevent new tasks from being claimed when worker or sandbox capacity is full. If sandbox capacity is full, sandbox tasks are skipped while non-sandbox queued tasks can still run.

The active task lifecycle is:

```text
CREATED
-> QUEUED
-> LEASED
-> SCHEDULED
-> PREPARING
-> SANDBOX_STARTING   only when a sandbox is requested
-> RUNNING
-> VERIFYING
-> SUCCEEDED / FAILED / CANCELLED
```

`TaskOrchestrator` owns the task-level lifecycle: it prepares the workspace, clones the repository when provided, starts and healthchecks the sandbox when requested, classifies the task, routes it to a runner, verifies the result, records metadata, and cleans sandbox resources.

The default container wires classification and routing:

- Simple analysis and report tasks route to `SingleAgentRunner`.
- Coding, implementation, test, build, and review tasks route to `SequentialRunner`.
- Architecture, system, parallel, and multi-agent tasks route to `SyncMultiAgentRunner`.
- `metadata.execution_mode` can force `single`, `sequential`, or `sync`.

Result metadata includes `execution.mode`, `execution.phases`, `sandbox`, and `verification` details so callers can inspect how the task was handled.
