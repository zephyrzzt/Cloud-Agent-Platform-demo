from __future__ import annotations


class ContextError(RuntimeError):
    pass


class ContextLaneNotFoundError(ContextError):
    pass
