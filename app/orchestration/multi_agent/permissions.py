from __future__ import annotations

from app.orchestration.multi_agent.roles import AgentRole


class MultiAgentPermissions:
    WRITE_PREFIXES = {
        AgentRole.MANAGER: {"plan", "decision", "status"},
        AgentRole.EXPLORER: {"finding", "risk", "question"},
        AgentRole.DEVELOPER: {"change", "implementation", "status"},
        AgentRole.REVIEWER: {"review", "defect", "approval", "status"},
    }

    def can_write(self, role: AgentRole, key: str) -> bool:
        allowed = self.WRITE_PREFIXES.get(role, set())
        prefix = key.split(":", 1)[0]
        return prefix in allowed
