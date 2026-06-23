# Tool Executors

Executors run validated and policy-approved tool requests.

Phase one implements `NativeExecutor`, which executes platform-owned Python tools. `ExecutorRouter` is present so later phases can route MCP and sandbox-backed tools without changing AgentLoop.
