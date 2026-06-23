# Bootstrap

Bootstrap wires the MVP application graph.

`create_container()` builds the in-memory task store, scheduler, lease manager, workspace manager, repository preparer, MVP mock runner, orchestrator, and worker. The API layer depends on this container instead of constructing services directly.

The FastAPI lifecycle starts the background worker when `TASK_WORKER_ENABLED` is true. The API request path only enqueues tasks and returns task metadata; clients poll task/result endpoints for completion.
