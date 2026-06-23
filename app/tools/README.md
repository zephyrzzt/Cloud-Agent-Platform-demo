# Tool System

The tool system is the controlled action pipeline between model decisions and real side effects.

Phase one includes:

- `models.py`: tool definitions, requests, results, context, and policy decisions.
- `registry.py`: native tool registration and lookup.
- `validator.py`: lightweight JSON-schema style argument validation.
- `policy.py`: role, write, and path-boundary checks.
- `native/`: built-in local tools.
- `executors/`: execution abstractions and the first native executor.

Models never execute actions directly. They return structured tool calls; the platform validates, authorizes, and executes those calls here.
