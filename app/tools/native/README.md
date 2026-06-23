# Native Tools

Native tools are platform-owned actions that can be executed without MCP.

Phase one includes basic workspace inspection, text search, artifact writing, and `finish_task`. Source write/edit tools exist, but the default registry only enables them when explicitly requested.

Sandbox command execution is available through controlled tools when `TaskOrchestrator` has started a task sandbox and passed its `sandbox_id` to the runner. The runner exposes `run_test`, `run_lint`, `run_build`, `run_compile`, and `run_program`; these tools map structured arguments to fixed command templates. Lifecycle, healthcheck, and cleanup stay in orchestration.
