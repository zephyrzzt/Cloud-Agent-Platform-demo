# Sandbox

The sandbox module defines the isolated execution plane used after repository preparation.

Phase two includes:

- `models.py`: structured sandbox, mount, resource, network, and command models.
- `policy.py`: image, network, environment, mount, timeout, and output-limit checks.
- `service.py`: provider-neutral sandbox service interface.
- `image_manager.py`: helper for building and checking the local Docker sandbox image.
- `healthcheck.py`: readiness checks for mounted directories, required tools, and non-root execution.
- `providers/docker.py`: Docker-backed sandbox provider.

The platform should depend on `SandboxService`, not directly on Docker.

Command execution is exposed through controlled tools when `SANDBOX_PROVIDER=docker` or a task-level `sandbox_provider` selects Docker: `run_test`, `run_lint`, `run_build`, `run_compile`, and `run_program`. `TaskOrchestrator` owns the sandbox lifecycle: it starts one sandbox for the task, waits for readiness, runs `SandboxHealthcheck`, passes the sandbox id to the runner, and removes the sandbox after the task finishes or fails.
