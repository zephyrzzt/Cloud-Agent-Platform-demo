# Cloud Agent Platform

Cloud Agent Platform 是一个面向代码仓库和综合任务的云端 Agent 执行平台。它接收代码仓库、本地路径或 GitHub 仓库 URL、目标分支或提交、自然语言任务、模型配置、执行限制以及可选的回调和文件设置，然后把任务放入一个可调度、可隔离、可执行、可验证的生命周期中。

这个项目的目标不是做一个简单的聊天机器人 Demo，而是搭建一个云端 Agent 平台骨架：控制面负责接收任务、排队调度、仓库准备、沙箱生命周期、模型选择、工具授权、结果验证和状态记录；执行面负责在受控 workspace 和 sandbox 中读取仓库、调用工具、运行测试或构建命令，并输出报告或文件产物。

The platform is designed for coding, repository analysis, report generation, code review, build/test automation, and mixed multi-step tasks.


For local setup, testing, API usage, Docker sandbox usage, and GitHub publishing steps, see `docs/operation-flow.md`.

## Current Focus

The current GitHub-ready baseline intentionally focuses on four areas. The goal of this version is to make the core platform loop visible and runnable: receive a task, prepare the workspace, optionally start a sandbox, route the task to the right Agent runner, let the model use validated tools, verify the result, and expose lifecycle/result/artifact APIs.

Other production hardening and future platform work is tracked in `docs/featurework.md`.

### 1. Agent Orchestration And Scheduling

This project treats an Agent task as a controlled platform job instead of a one-off model call. A task goes through queueing, leasing, preparation, sandbox startup, Agent execution, verification, result recording, and cleanup.

Main files:

- `app/orchestration/task_scheduler.py`: selects queued tasks by priority and capacity.
- `app/orchestration/task_worker.py`: leases a task, renews the lease, runs the orchestrator, and records success or failure.
- `app/orchestration/task_orchestrator.py`: owns the full task lifecycle and connects workspace, sandbox, runner, verification, and cleanup.
- `app/orchestration/task_state_machine.py`: keeps lifecycle transitions explicit and timestamped.
- `app/orchestration/task_classifier.py`: classifies user requests into task types.
- `app/orchestration/execution_router.py`: chooses the execution mode.
- `app/orchestration/runners/`: contains single-agent, sequential, and sync multi-agent runners.

Implemented orchestration capabilities:

- `POST /tasks` creates a task and stores it in the task queue.
- `TaskScheduler` supports priority ordering, max concurrent task limits, and sandbox capacity limits.
- `TaskWorker` leases a task before execution and periodically heartbeats the lease during long-running work.
- `TaskOrchestrator` owns this lifecycle:
  `QUEUED -> LEASED -> SCHEDULED -> PREPARING -> SANDBOX_STARTING -> RUNNING -> VERIFYING -> SUCCEEDED/FAILED`.
- `/tasks/{task_id}/events` exposes lifecycle timestamps so callers can inspect progress.
- `TaskClassifier` and `ExecutionRouter` decide whether a task should run as single-agent, sequential multi-phase, or sync multi-agent execution.
- `SingleAgentRunner`, `SequentialRunner`, and `SyncMultiAgentRunner` are wired into the default application container.
- `metadata.execution_mode` can force `single`, `sequential`, or `sync` routing when a caller wants explicit control.

Why this matters:

- The platform can process tasks through a repeatable lifecycle instead of ad hoc scripts.
- Scheduling and leases create a clear foundation for worker pools, retries, recovery, queue policies, and task cancellation.
- Orchestration gives the platform one central place to coordinate repository preparation, sandbox startup, model/tool execution, verification, result metadata, and cleanup.

### 2. Sandbox And Isolated Execution

The platform separates trusted control-plane work from untrusted repository execution. The API, scheduler, and orchestrator prepare and supervise the task, while repository code and command execution are pushed into a controlled workspace/sandbox boundary.

Main files:

- `app/workspace/workspace_manager.py`: creates task-local workspace, artifact, log, and metadata directories.
- `app/workspace/repository_preparer.py`: clones or checks out local and remote repositories.
- `app/sandbox/models.py`: defines sandbox, mount, resource, network, and command models.
- `app/sandbox/policy.py`: validates sandbox command and path behavior.
- `app/sandbox/healthcheck.py`: checks whether a sandbox is ready before Agent execution.
- `app/sandbox/service.py`: provider-neutral sandbox service contract.
- `app/sandbox/providers/docker.py`: Docker-backed sandbox provider.
- `app/tools/native/command_tools.py`: exposes controlled command tools to the Agent.

Implemented sandbox capabilities:

- Each task receives its own workspace under `.local/workspaces/{task_id}`.
- Repository input can be a local path or GitHub URL and is prepared before the Agent starts.
- Docker sandbox support starts one sandbox per task when `SANDBOX_PROVIDER=docker`.
- `TaskOrchestrator` performs sandbox startup, readiness wait, healthcheck, runner handoff, and cleanup.
- Repository files are mounted read-only, while artifact output is mounted writable.
- Free-form `run_command` is not exposed to the Agent. Command execution is limited to these controlled tools:
  `run_test`, `run_lint`, `run_build`, `run_compile`, and `run_program`.
- Sandbox lifecycle evidence is recorded in task result metadata under `metadata.sandbox`.

Why this matters:

- User code does not run directly in the API or scheduler process.
- The command surface is intentionally constrained, which makes tool calls easier to validate, audit, reproduce, and verify.
- The sandbox lifecycle belongs to the orchestrator, so tool execution uses an already-created task sandbox rather than starting unmanaged containers.
- The same sandbox interface can later support Kubernetes, Firecracker, or other providers without changing Agent orchestration code.

### 3. LLM Integration And Tool Calling

The model is treated as a decision-making component, while every real action goes through structured tools, validation, authorization, execution, and verification. This keeps the Agent flexible without giving the model direct access to the host machine.

Main files:

- `app/orchestration/agent_loop.py`: drives model requests, tool calls, tool results, and final task completion.
- `app/llm/models.py`: defines provider-neutral model messages, tool calls, and responses.
- `app/llm/providers/mock.py`: deterministic local provider for tests and demos.
- `app/llm/providers/openai_compatible.py`: real OpenAI-compatible `/chat/completions` provider.
- `app/llm/router.py`: selects the configured model provider.
- `app/tools/registry.py`: registers platform tools.
- `app/tools/validator.py`: validates tool names and arguments.
- `app/tools/policy.py`: authorizes tool calls based on the task context.
- `app/tools/executors/`: routes validated tool calls to native or future external executors.

Implemented LLM and tool capabilities:

- Provider-neutral model request and response models.
- Deterministic `MockProvider` for local testing without API keys.
- OpenAI-compatible `/chat/completions` provider for real model calls.
- Per-task `model_provider` and `model_name` overrides through the API.
- Tool schema registration, validation, policy checks, and executor routing.
- Native tools for reading/searching files, writing artifacts, finishing tasks, and controlled sandbox commands.
- Real-provider tool-call flow where the model can call `write_artifact`, use sandbox command tools, and then call `finish_task`.
- Deterministic verification checks whether required artifacts or command evidence were produced before the task is marked successful.

Why this matters:

- The Agent can use models from different providers behind a shared interface.
- Tool calls are explicit platform operations, so the system can inspect, restrict, execute, log, and verify them.
- Local mock execution and real model execution use the same AgentLoop path, making the project easier to test and extend.
- Tool policy and executor routing provide the future boundary for MCP tools, remote tools, reviewer debug permissions, and risk-based tool gating.

### 4. Overall Architecture And Extensibility

The repository is organized around replaceable platform boundaries instead of one large script. The current implementation uses in-memory stores and simple providers where appropriate, but the boundaries are already shaped so later production components can replace them.

Implemented architecture capabilities:

- `app/bootstrap` builds the default dependency container.
- `app/api` exposes task creation, result, artifact, and lifecycle event endpoints.
- `app/orchestration` contains scheduler, worker, orchestrator, runners, routing, leases, state machine, and multi-agent coordination.
- `app/workspace` prepares per-task directories and repositories.
- `app/sandbox` defines provider-neutral sandbox models, policies, service interface, healthcheck, and Docker implementation.
- `app/llm` contains model abstractions, providers, and routing.
- `app/tools` contains tool definitions, validation, policy, native tools, and executors.
- `app/verification` performs independent result checks before a task is marked successful.
- `app/context`, `app/file_storage`, `app/event_callback`, `app/pending_messages`, `app/storage`, and `app/integrations/mcp` provide extension points for later production features.

Why this matters:

- The current code can run as a first-version local platform while still leaving clear extension points for production services.
- In-memory components can later be replaced by database-backed storage without rewriting the API or orchestrator flow.
- Sandbox providers, model providers, tool executors, verification rules, and runners can evolve independently.
- The project layout makes it clear which code belongs to the control plane, execution plane, model layer, tool layer, storage layer, and integration layer.

## Usage Tutorial

This section shows the shortest path to run the platform locally. For the full end-to-end guide, see `docs/operation-flow.md`.

### 1. Install Dependencies

Clone your GitHub repository and enter the project directory:

```powershell
git clone https://github.com/zephyrzzt/Cloud-Agent-Platform-demo.git
cd Cloud-Agent-Platform-demo
python -m pip install -r requirements.txt
```

Run the test suite:

```powershell
python -m pytest -q
```

Expected result:

```text
52 passed, 1 warning
```

The warning comes from the FastAPI test client dependency and does not block local use.

### 2. Start The API

The default configuration uses `MockProvider`, so no model API key or Docker installation is required for the first run.

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open. The FastAPI app starts a background worker that picks queued tasks and runs them through the orchestrator.

### 3. Create A Simple Task

Open a second PowerShell window and submit a task:

```powershell
$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body '{"prompt":"Create a short MVP report.","allow_write":false}'

$task
```

Check lifecycle events:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/events
```

Check the final result:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/result
```

List generated artifacts:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/artifacts
```

Read the generated report:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/artifacts/report.md
```

Expected behavior:

- The task moves through the orchestrator lifecycle and ends as `succeeded`.
- `report.md` is generated under the task artifact directory.
- Result metadata contains verification details.

### 4. Submit A Repository Task

The API can receive a local repository path or a GitHub repository URL. The worker prepares the repository under `.local/workspaces/{task_id}/repository` before the Agent starts.

Use a local repository:

```powershell
$body = @{
  prompt = "Inspect the repository and create report.md with a short summary."
  repository = @{
    url = "C:\path\to\your\repo"
  }
  metadata = @{
    requires_artifact = $true
    expected_artifacts = @("report.md")
  }
} | ConvertTo-Json -Depth 5

$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body $body
```

Use a public GitHub repository:

```powershell
$body = @{
  prompt = "Inspect the repository and create report.md with a short summary."
  repository = @{
    url = "https://github.com/owner/repo.git"
    ref = "main"
  }
  metadata = @{
    requires_artifact = $true
    expected_artifacts = @("report.md")
  }
} | ConvertTo-Json -Depth 5
```

For private repositories, pass credentials only through local environment variables or local-only scripts. Do not commit real tokens to GitHub.

### 5. Use A Real OpenAI-Compatible Model

Set model environment variables before starting the API:

```powershell
$env:DEFAULT_MODEL_PROVIDER="openai_compatible"
$env:DEFAULT_MODEL_NAME="your-model-name"
$env:OPENAI_COMPATIBLE_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_COMPATIBLE_API_KEY="your-api-key"
```

Then submit a task that asks the model to produce an artifact and finish:

```powershell
$body = @{
  prompt = "Create report.md as an artifact with a short project status summary, then finish the task."
  model_provider = "openai_compatible"
  model_name = "your-model-name"
  metadata = @{
    requires_artifact = $true
    expected_artifacts = @("report.md")
  }
} | ConvertTo-Json -Depth 5

$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body $body
```

The model should call `write_artifact` to save output and `finish_task` to end the Agent loop.

### 6. Enable Docker Sandbox Execution

Start Docker Desktop, then build the sandbox image:

```powershell
docker build -t cloud-agent-sandbox:latest -f sandbox/Dockerfile sandbox
```

Enable the Docker sandbox:

```powershell
$env:SANDBOX_PROVIDER="docker"
$env:SANDBOX_IMAGE="cloud-agent-sandbox:latest"
$env:SANDBOX_NETWORK="none"
```

Submit a sandbox command task:

```powershell
$body = @{
  prompt = "Use run_compile with language python and path . to check Python files. Save report.md with the command output, then finish the task."
  model_provider = "openai_compatible"
  model_name = "your-model-name"
  sandbox_provider = "docker"
  sandbox_image = "cloud-agent-sandbox:latest"
  metadata = @{
    requires_command = $true
    requires_artifact = $true
    expected_artifacts = @("report.md")
  }
} | ConvertTo-Json -Depth 5

$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body $body
```

In this mode, `TaskOrchestrator` starts the sandbox, healthchecks it, passes controlled command tools to the Agent, verifies command evidence, and removes the sandbox when the task finishes.

## Core Ideas

- Separate the control plane from the execution plane.
- Keep user code execution inside an isolated sandbox.
- Let LLMs make decisions, but route all actions through validated tools.
- Support single-agent and multi-agent execution modes.
- Share multi-agent state through a structured blackboard instead of full chat history.
- Use independent verification before marking a task complete.
- Persist task events, messages, logs, reports, and artifacts.

## High-Level Flow

```text
API / CLI / Frontend
-> Pending Messages
-> Task Scheduler
-> Task Worker
-> Task Orchestrator
-> Workspace + Sandbox
-> Task Classifier
-> Execution Router
-> Agent Runner
-> Agent Loop
-> Model Provider
-> Tool Validator
-> Tool Policy
-> Tool Executor
-> Verifier
-> File Store
-> Notification + Cleanup
```

## Execution Modes

- Single: one agent loop handles a simple task.
- Sequential: Explorer, Developer, and Reviewer run in order.
- Sync multi-agent: Manager delegates phases to role-specific agents through a blackboard.

## Project Structure

```text
Cloud-Agent-Platform-demo/
  app/
    api/                  HTTP APIs, WebSocket entry points, task/result/artifact endpoints
    bootstrap/            dependency container, application wiring, startup/shutdown lifecycle
    config/               environment-based settings and runtime configuration
    domain/               task, repository, conversation, and event domain models
    orchestration/        scheduler, worker, orchestrator, state machine, runners, routing
    workspace/            per-task workspace creation and repository preparation
    sandbox/              sandbox models, policy, healthcheck, service interface, providers
    llm/                  model abstractions, provider registry, routing, adapters, providers
    tools/                tool definitions, validation, policy, native tools, executor routing
    verification/         deterministic checks before a task is marked successful
    context/              context lanes, token budgets, compaction, recall, file buffering
    storage/              in-memory task, event, and conversation store interfaces
    pending_messages/     reliable frontend/client message buffering and replay
    event_callback/       callback configuration, signing, dispatch, retry, worker flow
    file_storage/         artifact/file storage abstraction and provider placeholders
    integrations/mcp/     MCP integration boundary and future external tool adapter layer
    observability/        logging, metrics, tracing, and audit extension points
  docs/                   design notes, operation flow, architecture notes, feature work
  sandbox/                Dockerfile and sandbox image build context
  tests/                  unit and integration-style tests for the current platform loop
  .github/workflows/      GitHub Actions test workflow
```

The code is split into platform layers:

- API layer: receives task requests, exposes task lifecycle, returns results, and serves generated artifacts.
- Control plane layer: schedules tasks, leases work, runs the orchestrator, records state, and decides execution mode.
- Workspace and sandbox layer: prepares repositories, starts isolated execution environments, exposes controlled command execution, and cleans up.
- Agent and model layer: routes tasks to runners, calls the selected model provider, and handles model tool calls.
- Tool layer: registers tools, validates arguments, applies policy, and routes execution to native or future external executors.
- Verification layer: checks platform evidence such as generated artifacts and command success before declaring a task successful.
- Extension layer: keeps placeholders and boundaries for persistent storage, callbacks, file storage, MCP, observability, and production providers.

## First Implementation Order

1. Agent loop, single-agent runner, mock model provider, tool registry, validator, policy, and native executor.
2. Workspace manager, repository preparer, sandbox service, Docker provider, sandbox policy, and healthcheck.
3. Task scheduler, worker, orchestrator, state machine, and execution lease.
4. Task classifier, execution router, task phases, and sequential runner.
5. Typed blackboard, Explorer, Developer, Reviewer, and failure ledger.
6. Reviewer debug mode and circuit breaker.
7. Context lanes, light/medium compaction, file buffer, and recall.
8. Sync multi-agent mode, heavy compaction, recovery, Kubernetes, and Firecracker.

## Current Status

Phase one is implemented:

- Agent loop and single-agent runner.
- Provider-neutral model request/response models.
- Deterministic mock model provider.
- Tool registry, validator, policy, native tools, and native executor.
- README files for the first-phase module folders.

Phase two is implemented:

- Workspace manager and repository preparer.
- Sandbox models, policy, service interface, and healthcheck.
- Docker sandbox provider with isolated container settings.
- README files for the phase-two module folders.

Phase three is implemented:

- Task domain model and in-memory task store.
- Task scheduler, worker, orchestrator, detailed lifecycle state machine, and execution lease manager.
- Orchestrator state flow: `QUEUED -> LEASED -> SCHEDULED -> PREPARING -> SANDBOX_STARTING -> RUNNING -> VERIFYING -> terminal`.
- Scheduler priority ordering, max concurrent task limits, sandbox capacity limits, and worker lease heartbeat are implemented.
- Compatibility exports for older LLM/tool module names.
- Pytest coverage for the first three phases.

Phase four through eight are implemented as first-version platform components:

- Task classifier, execution router, task phases, sequential runner, and sync multi-agent runner are wired into the default container.
- Typed blackboard, role permissions, delegation, multi-agent coordinator, and failure ledger.
- Reviewer debug grants and failure circuit breaker.
- Context lanes, compaction policy, compactors, file buffer, and recall.
- Recovery service plus Kubernetes and Firecracker provider placeholders behind the sandbox interface.

MVP API flow is implemented:

- `POST /tasks` creates and queues a task.
- `POST /tasks` accepts `priority`; higher priority tasks are selected before lower priority tasks when capacity allows.
- `POST /tasks` can include a `repository` payload; the worker clones or checks it out under `.local/workspaces/{task_id}/repository` before agent execution.
- FastAPI lifecycle starts a background worker to process queued tasks.
- The MVP runner uses `MockProvider` to write `report.md` and call `finish_task`.
- `GET /tasks/{task_id}/result` returns the completed task result.
- `GET /tasks/{task_id}/events` returns lifecycle events for queued, scheduled, preparing, sandbox_starting, running, verifying, and terminal states when timestamps exist.
- Artifact listing and reading endpoints expose generated task artifacts.
- Task result metadata exposes workspace paths, repository path, requested ref, and resolved commit when a repository is provided.
- Task result metadata also exposes `execution.mode`, `execution.phases`, sandbox healthcheck/cleanup, and verification results.

Default runner routing is wired:

- Simple analysis and report tasks use `SingleAgentRunner`.
- Coding, implementation, testing, build, and review tasks use `SequentialRunner`.
- Architecture, system, parallel, and multi-agent tasks use `SyncMultiAgentRunner`.
- Requests can force routing with `metadata.execution_mode` set to `single`, `sequential`, or `sync`.

Model selection is wired:

- `DEFAULT_MODEL_PROVIDER=mock` keeps the deterministic scripted MVP behavior.
- `DEFAULT_MODEL_PROVIDER=openai_compatible` routes AgentLoop through the OpenAI-compatible `/chat/completions` provider.
- `POST /tasks` can also pass `model_provider` and `model_name`; omitted values use settings defaults.
- Real-provider tool calls are supported for OpenAI-compatible responses. The model can call `write_artifact` to save task output, then call `finish_task` to mark the run complete.
- Per-task `model_name` values are forwarded into provider requests, so API callers can override the configured default model for a task.

Sandbox command execution is wired:

- `SANDBOX_PROVIDER=disabled` keeps command execution tools hidden.
- `SANDBOX_PROVIDER=docker` starts one Docker sandbox per task, runs healthcheck, exposes controlled command tools to the agent, and cleans the sandbox after the task finishes.
- The agent can use `run_test`, `run_lint`, `run_build`, `run_compile`, and `run_program`; it no longer receives a free-form `run_command` shell tool.
- `SANDBOX_IMAGE=cloud-agent-sandbox:latest` selects the image used by the command sandbox.
- `POST /tasks` can pass `sandbox_provider` and `sandbox_image` for per-task sandbox selection.
- Build the local sandbox image with `docker build -t cloud-agent-sandbox:latest -f sandbox/Dockerfile sandbox`.
- Result metadata stores sandbox lifecycle evidence under `metadata.sandbox`, including healthcheck and cleanup status.

Verification is wired:

- The orchestrator now runs a deterministic verification service before marking a completed agent run as succeeded.
- Report/file/summary tasks must produce artifacts.
- Test or command tasks must have a successful controlled command tool result.
- Verification details are stored under task result metadata as `verification`.
- Task metadata can set `requires_artifact`, `requires_command`, and `expected_artifacts` to make checks explicit.
- Keyword-based verification uses English keywords only; non-English prompts should use explicit metadata flags for deterministic checks.

Remaining work outside the current scope is tracked in `docs/featurework.md`.
