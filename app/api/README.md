# API

The MVP API exposes the first vertical task flow:

- `POST /tasks`: create and enqueue a task. Optional `priority` controls scheduler ordering; higher values run first.
- `GET /tasks/{task_id}`: read task status.
- `GET /tasks/{task_id}/result`: read final task result.
- `GET /tasks/{task_id}/events`: return synthetic lifecycle events from task timestamps, including queued, scheduled, preparing, sandbox_starting, running, verifying, and terminal events when available.
- `GET /tasks/{task_id}/artifacts`: list generated artifacts.
- `GET /tasks/{task_id}/artifacts/{path}`: read a generated text artifact.

Tasks are processed by the background worker started in the FastAPI lifecycle. Storage is still in-memory, so this proves the platform flow before adding persistence, WebSockets, and callbacks.
