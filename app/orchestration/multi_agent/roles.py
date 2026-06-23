from __future__ import annotations

from enum import StrEnum


class AgentRole(StrEnum):
    MANAGER = "manager"
    EXPLORER = "explorer"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
