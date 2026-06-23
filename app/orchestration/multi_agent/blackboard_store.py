from __future__ import annotations

import asyncio

from app.orchestration.multi_agent.blackboard import Blackboard


class BlackboardStore:
    def __init__(self) -> None:
        self._boards: dict[str, Blackboard] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, task_id: str) -> Blackboard:
        async with self._lock:
            board = self._boards.get(task_id)
            if board is None:
                board = Blackboard()
                self._boards[task_id] = board
            return board

    async def get(self, task_id: str) -> Blackboard | None:
        async with self._lock:
            return self._boards.get(task_id)
