from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(RuntimeError):
    pass


class WorkspacePathError(WorkspaceError):
    pass


@dataclass(frozen=True)
class WorkspaceLayout:
    task_id: str
    root: Path
    repository: Path
    artifacts: Path
    logs: Path
    metadata: Path

    def ensure_created(self) -> "WorkspaceLayout":
        for path in [
            self.root,
            self.repository,
            self.artifacts,
            self.logs,
            self.metadata,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        return self

    def resolve_inside(self, raw_path: str | Path) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspacePathError(
                f"Path is outside workspace root: {raw_path}"
            ) from exc
        return resolved


class WorkspaceManager:
    def __init__(self, root: str | Path = ".local/workspaces") -> None:
        self.root = Path(root).resolve()

    def create_workspace(self, task_id: str) -> WorkspaceLayout:
        self._validate_task_id(task_id)
        layout = self.get_workspace(task_id)
        return layout.ensure_created()

    def get_workspace(self, task_id: str) -> WorkspaceLayout:
        self._validate_task_id(task_id)
        task_root = (self.root / task_id).resolve()
        try:
            task_root.relative_to(self.root)
        except ValueError as exc:
            raise WorkspacePathError(f"Invalid task id: {task_id}") from exc

        return WorkspaceLayout(
            task_id=task_id,
            root=task_root,
            repository=task_root / "repository",
            artifacts=task_root / "artifacts",
            logs=task_root / "logs",
            metadata=task_root / "metadata",
        )

    def cleanup_workspace(self, task_id: str) -> bool:
        layout = self.get_workspace(task_id)
        if not layout.root.exists():
            return False
        shutil.rmtree(layout.root)
        return True

    def _validate_task_id(self, task_id: str) -> None:
        if not task_id or task_id in {".", ".."}:
            raise WorkspacePathError("task_id must be a non-empty path segment")
        if "/" in task_id or "\\" in task_id:
            raise WorkspacePathError("task_id cannot contain path separators")
