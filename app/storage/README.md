# Storage

Storage modules persist platform metadata.

Phase three includes an in-memory `TaskStore` implementation. It is intentionally small and async-safe so the scheduler and worker can be tested without a database. Later phases can replace it with SQLite or PostgreSQL behind the same task-store behavior.
