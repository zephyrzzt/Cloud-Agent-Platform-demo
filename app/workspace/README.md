# Workspace

The workspace module prepares task-local directories before any agent execution.

Phase two includes:

- `WorkspaceManager`: creates and cleans per-task roots with `repository`, `artifacts`, `logs`, and `metadata` subdirectories.
- `RepositoryPreparer`: validates repository inputs, clones the requested ref, disables interactive Git prompts, and keeps access tokens out of model context.

Repository preparation belongs to the trusted control plane, before sandboxed agent execution begins.
