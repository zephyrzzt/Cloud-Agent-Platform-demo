from __future__ import annotations

from app.orchestration.multi_agent.models import BlackboardItem
from app.orchestration.multi_agent.permissions import MultiAgentPermissions
from app.orchestration.multi_agent.roles import AgentRole


class BlackboardPermissionError(RuntimeError):
    pass


class Blackboard:
    def __init__(
        self,
        *,
        permissions: MultiAgentPermissions | None = None,
    ) -> None:
        self.permissions = permissions or MultiAgentPermissions()
        self._items: dict[str, BlackboardItem] = {}

    def write(self, key: str, value, role: AgentRole) -> BlackboardItem:
        if not self.permissions.can_write(role, key):
            raise BlackboardPermissionError(f"{role} cannot write blackboard key {key}")

        previous = self._items.get(key)
        item = BlackboardItem(
            key=key,
            value=value,
            role=role,
            version=1 if previous is None else previous.version + 1,
        )
        self._items[key] = item
        return item

    def read(self, key: str):
        item = self._items.get(key)
        return None if item is None else item.value

    def item(self, key: str) -> BlackboardItem | None:
        return self._items.get(key)

    def snapshot(self) -> dict[str, object]:
        return {key: item.value for key, item in self._items.items()}

    def list_items(self) -> list[BlackboardItem]:
        return list(self._items.values())
