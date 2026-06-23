from __future__ import annotations


class OrchestrationError(RuntimeError):
    pass


class InvalidTaskTransitionError(OrchestrationError):
    pass


class ExecutionLeaseError(OrchestrationError):
    pass


class ExecutionLeaseNotAcquiredError(ExecutionLeaseError):
    pass


class TaskExecutionError(OrchestrationError):
    pass
