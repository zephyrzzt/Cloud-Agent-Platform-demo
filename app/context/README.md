# Context

Context is separated into lanes so agents do not need to share full histories.

Phase seven includes:

- `ContextLane`: per-role context entry storage.
- `ContextBudget` and `CompactionPolicy`: decide when to compact.
- `ContextCompactor`: light, medium, and heavy compaction.
- `FileBuffer`: unloads large content to files while keeping references.
- `RecallService`: keyword recall across lanes and buffered files.
