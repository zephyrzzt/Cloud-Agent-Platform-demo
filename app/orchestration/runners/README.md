# Agent Runners

Runners adapt orchestration flows to a task execution mode.

Phase one includes `SingleAgentRunner`, a thin wrapper around `AgentLoop`.

Later phases add `SequentialRunner` for Explorer -> Developer -> Reviewer execution and `SyncMultiAgentRunner` for Manager-style coordination through a blackboard.
