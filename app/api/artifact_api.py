from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.api.task_api import get_container


router = APIRouter(tags=["artifacts"])


@router.get("/tasks/{task_id}/artifacts")
async def list_artifacts(task_id: str, request: Request) -> dict:
    task = await get_container(request).task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.result is None:
        return {"task_id": task_id, "artifacts": []}
    return {"task_id": task_id, "artifacts": task.result.artifact_paths}


@router.get("/tasks/{task_id}/artifacts/{artifact_path:path}")
async def get_artifact(
    task_id: str,
    artifact_path: str,
    request: Request,
) -> PlainTextResponse:
    task = await get_container(request).task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.workspace_root is None:
        raise HTTPException(status_code=404, detail="Task workspace not found")

    artifact_root = Path(task.workspace_root) / "artifacts"
    candidate = (artifact_root / artifact_path).resolve()
    try:
        candidate.relative_to(artifact_root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid artifact path") from exc

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return PlainTextResponse(candidate.read_text(encoding="utf-8"))
