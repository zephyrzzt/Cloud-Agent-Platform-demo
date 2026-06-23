from __future__ import annotations

from app.context.errors import ContextLaneNotFoundError
from app.context.lane import ContextLane
from app.context.models import ContextRole


class ContextManager:
    def __init__(self) -> None:
        self._lanes: dict[ContextRole, ContextLane] = {
            role: ContextLane(role) for role in ContextRole
        }

    def lane(self, role: ContextRole | str) -> ContextLane:
        role = ContextRole(role)
        try:
            return self._lanes[role]
        except KeyError as exc:
            raise ContextLaneNotFoundError(f"Context lane not found: {role}") from exc

    def append(
        self,
        role: ContextRole | str,
        content: str,
        *,
        entry_role: str = "note",
        metadata: dict | None = None,
    ):
        return self.lane(role).append(content, role=entry_role, metadata=metadata)

    def snapshots(self):
        return {role.value: lane.snapshot() for role, lane in self._lanes.items()}
