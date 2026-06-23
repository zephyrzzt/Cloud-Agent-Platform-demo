# Cloud Agent Platform Operation Flow

This document describes the end-to-end local workflow for testing and using the current first-version platform.

## 1. Prepare The Project

Clone your GitHub repository and enter the project directory:

```powershell
git clone https://github.com/your-name/your-repo.git
cd your-repo
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the full test suite:

```powershell
python -m pytest -q
```

Expected result:

```text
52 passed, 1 warning
```

The warning is from the FastAPI test client dependency and does not block local use.

## 2. Run The Default Mock Flow

The mock flow does not require an API key or Docker. It is the quickest way to confirm that the API, worker, agent loop, artifacts, and verification are connected.

Start the API:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open a second PowerShell window and create a task:

```powershell
$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body '{"prompt":"Create a short MVP report.","allow_write":false}'

$task
```

Check the result:

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

- The task reaches `succeeded`.
- `report.md` is generated.
- Result metadata includes `verification.passed = true`.

## 3. Use A Real OpenAI-Compatible Model

Set environment variables in the same PowerShell window that will start the API:

```powershell
$env:DEFAULT_MODEL_PROVIDER="openai_compatible"
$env:DEFAULT_MODEL_NAME="your-model-name"
$env:OPENAI_COMPATIBLE_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_COMPATIBLE_API_KEY="your-api-key"
```

Start the API:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Submit a task that asks the model to save an artifact:

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

Check the result and report:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/result
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/artifacts/report.md
```

Expected behavior:

- The model calls `write_artifact`.
- The model calls `finish_task`.
- Verification passes only if `report.md` exists.

## 4. Submit A Task With Repository Input

When the request includes `repository`, the worker creates a task workspace and clones or checks out the repository before the agent starts.

Workspace layout:

```text
.local/workspaces/{task_id}/
  repository/
  artifacts/
  logs/
  metadata/
```

For a local repository:

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

For a public GitHub repository:

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

For a private HTTPS repository, pass an access token in the repository payload:

```powershell
$body = @{
  prompt = "Inspect the repository and create report.md with a short summary."
  repository = @{
    url = "https://github.com/owner/private-repo.git"
    ref = "main"
    access_token = "your-token"
  }
  metadata = @{
    requires_artifact = $true
    expected_artifacts = @("report.md")
  }
} | ConvertTo-Json -Depth 5
```

Do not commit real access tokens to GitHub. Use environment variables or local-only scripts for real credentials.

Check the result:

```powershell
$result = Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/result
$result.metadata.workspace
$result.metadata.repository
```

Expected repository metadata:

```text
provided        : True
path            : .local/workspaces/{task_id}/repository
requested_url   : repository URL with credentials redacted
requested_ref   : requested branch, tag, or commit
resolved_commit : actual checked-out commit
```

The agent receives `.local/workspaces/{task_id}/repository` as its workspace root, so tools such as `list_files`, `read_file`, `search_code`, and controlled sandbox command tools operate on the prepared repository.

## 5. Build And Use The Docker Sandbox

Start Docker Desktop first.

Build the sandbox image:

```powershell
docker build -t cloud-agent-sandbox:latest -f sandbox/Dockerfile sandbox
```

Confirm the image exists:

```powershell
docker image inspect cloud-agent-sandbox:latest
```

Set sandbox environment variables:

```powershell
$env:SANDBOX_PROVIDER="docker"
$env:SANDBOX_IMAGE="cloud-agent-sandbox:latest"
$env:SANDBOX_NETWORK="none"
```

Use a real model for sandbox tasks, because the default mock provider only writes a report and does not call controlled command tools.

Submit a command task:

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

Check the result:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.task_id)/result
```

Expected behavior:

- The model can see `run_test`, `run_lint`, `run_build`, `run_compile`, and `run_program`.
- `TaskOrchestrator` starts one Docker sandbox for the task.
- The sandbox reaches running state and passes healthcheck before the agent starts.
- Controlled command tools execute inside the existing task sandbox.
- The repository is mounted read-only.
- Artifacts are mounted writable.
- The sandbox is removed after the task finishes or fails.
- Result metadata includes `sandbox.healthcheck.ok = true` and `sandbox.cleanup.deleted = true`.
- Verification passes only if a controlled command tool succeeds and `report.md` exists.

## 6. Understand The Runtime Flow

The current request lifecycle is:

```text
POST /tasks
-> TaskScheduler queues the task
-> TaskWorker leases the task
-> TaskOrchestrator creates a workspace
-> RepositoryPreparer clones/checks out the repository when provided
-> TaskOrchestrator starts and healthchecks the task sandbox when requested
-> ConfigurableAgentRunner selects the model and sandbox tools
-> AgentLoop sends messages and tool schemas to the model
-> ToolExecutor validates, authorizes, and executes tool calls
-> Agent calls finish_task
-> BasicVerificationService checks artifacts and command evidence
-> TaskOrchestrator cleans the task sandbox when one was started
-> Task is marked succeeded or failed
-> Result and artifacts are exposed through API endpoints
```

Scheduler behavior:

- `priority` in `POST /tasks` controls queued task order; higher values run first.
- `TASK_SCHEDULER_MAX_CONCURRENT_TASKS` limits active leased/running/verifying tasks.
- `TASK_SCHEDULER_MAX_SANDBOX_TASKS` limits active tasks that request a sandbox.
- `TASK_WORKER_LEASE_TTL_SECONDS` controls lease expiration.
- `TASK_WORKER_LEASE_HEARTBEAT_INTERVAL_SECONDS` controls how often the worker renews a lease during long tasks.

## 7. Useful Test Commands

Run everything:

```powershell
python -m pytest -q
```

Run API tests:

```powershell
python -m pytest tests\test_api_mvp.py -q
```

Run model routing and OpenAI-compatible provider tests:

```powershell
python -m pytest tests\test_llm_router.py tests\test_openai_compatible_provider.py tests\test_real_model_tool_flow.py -q
```

Run sandbox command tests:

```powershell
python -m pytest tests\test_sandbox_command_tool.py -q
```

Run verification tests:

```powershell
python -m pytest tests\test_verification.py -q
```

## 8. Initialize Git For GitHub

Check whether this directory is already a Git repository:

```powershell
cd your-repo
git status
```

If `git status` says the directory is not a Git repository, initialize it:

```powershell
git init
git status
```

When `git status` works, make the first commit:

```powershell
git add .
git commit -m "Initial cloud agent platform implementation"
```

Then create an empty GitHub repository and connect it:

```powershell
git branch -M main
git remote add origin https://github.com/your-name/your-repo.git
git push -u origin main
```

## 9. Current Limits

- The default task store is in memory, so tasks disappear when the API process stops.
- Docker sandbox support requires Docker Desktop.
- Kubernetes and Firecracker providers are placeholders.
- Real model behavior depends on whether the model follows tool-call instructions.
- Verification is deterministic and rule-based; it checks platform evidence, not semantic code quality.
- Work outside the current four-area baseline is tracked in `docs/featurework.md`.
