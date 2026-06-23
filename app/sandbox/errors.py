from __future__ import annotations


class SandboxError(RuntimeError):
    pass


class SandboxNotFoundError(SandboxError):
    pass


class SandboxNotReadyError(SandboxError):
    pass


class SandboxStartError(SandboxError):
    pass


class SandboxExecutionError(SandboxError):
    pass


class SandboxTimeoutError(SandboxExecutionError):
    pass


class SandboxPolicyViolationError(SandboxError):
    pass


class SandboxResourceLimitError(SandboxError):
    pass
