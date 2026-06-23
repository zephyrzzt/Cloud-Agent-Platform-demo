# Sandbox Providers

Providers implement the `SandboxService` interface for concrete runtimes.

Phase two includes `DockerSandboxService`, which uses the Docker CLI to create an isolated container with non-root execution, read-only root filesystem, read-only repository mount, writable artifact mount, disabled network by default, resource limits, no-new-privileges, and dropped Linux capabilities.

The Docker provider is now connected to the agent tool layer through controlled command tools. Build the default image from `sandbox/Dockerfile`, then set `SANDBOX_PROVIDER=docker` and `SANDBOX_IMAGE=cloud-agent-sandbox:latest`.

Phase eight adds interface-complete Kubernetes and Firecracker placeholders. They intentionally raise explicit "not enabled" errors until real runtime integration is provided.
