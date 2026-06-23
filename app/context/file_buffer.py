from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class BufferedFile:
    id: str
    path: Path
    description: str


class FileBuffer:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, BufferedFile] = {}

    def write(self, content: str, *, description: str = "") -> BufferedFile:
        item_id = uuid4().hex
        path = self.root / f"{item_id}.txt"
        path.write_text(content, encoding="utf-8")
        item = BufferedFile(id=item_id, path=path, description=description)
        self._items[item_id] = item
        return item

    def read(self, item_id: str) -> str:
        item = self._items[item_id]
        return item.path.read_text(encoding="utf-8")

    def list(self) -> list[BufferedFile]:
        return list(self._items.values())
