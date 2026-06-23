# Multi-Agent

This package contains the first structured multi-agent coordination layer.

- `roles.py`: Manager, Explorer, Developer, and Reviewer roles.
- `blackboard.py`: typed shared state with role-based write boundaries.
- `blackboard_store.py`: task-scoped blackboard storage.
- `delegation.py`: delegates a phase to a role runner.
- `coordinator.py`: runs phase-role assignments and records summaries in the blackboard.

Agents exchange structured blackboard entries instead of sharing full chat histories.
