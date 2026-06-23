from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.bootstrap.container import AppContainer
from app.domain.task import RepositoryRef, TaskLimits, TaskRequest, TaskStatus, TaskType


router = APIRouter(tags=["tasks"])


class RepositoryPayload(BaseModel):
    url: str
    ref: str | None = None
    access_token: str | None = None


class CreateTaskPayload(BaseModel):
    prompt: str = Field(..., min_length=1)
    allow_write: bool = False
    task_type: TaskType = TaskType.MIXED
    priority: int = 0
    model_provider: str | None = None
    model_name: str | None = None
    sandbox_provider: str | None = None
    sandbox_image: str | None = None
    repository: RepositoryPayload | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: str
    updated_at: str
    error: str | None = None


class TaskResultResponse(BaseModel):
    task_id: str
    status: TaskStatus
    summary: str = ""
    artifact_paths: list[str] = Field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


@router.post("/tasks", response_model=TaskResponse)
async def create_task(payload: CreateTaskPayload, request: Request) -> TaskResponse:
    container = get_container(request)
    repository = None
    if payload.repository is not None:
        repository = RepositoryRef(
            url=payload.repository.url,
            ref=payload.repository.ref,
            access_token=payload.repository.access_token,
        )

    task = await container.scheduler.submit(
        TaskRequest(
            prompt=payload.prompt,
            repository=repository,
            task_type=payload.task_type,
            priority=payload.priority,
            allow_write=payload.allow_write,
            model_provider=payload.model_provider
            or container.settings.default_model_provider,
            model_name=payload.model_name or container.settings.default_model_name,
            sandbox_provider=payload.sandbox_provider
            or container.settings.sandbox_provider,
            sandbox_image=payload.sandbox_image or container.settings.sandbox_image,
            limits=TaskLimits(),
            metadata=payload.metadata,
        )
    )
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        error=task.error,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, request: Request) -> TaskResponse:
    task = await get_container(request).task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        error=task.error,
    )


@router.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(task_id: str, request: Request) -> TaskResultResponse:
    task = await get_container(request).task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.result is None:
        return TaskResultResponse(
            task_id=task.id,
            status=task.status,
            error=task.error,
        )

    return TaskResultResponse(
        task_id=task.id,
        status=task.status,
        summary=task.result.summary,
        artifact_paths=task.result.artifact_paths,
        error=task.result.error,
        metadata=task.result.metadata,
    )


@router.get("/tasks/{task_id}/events")
async def get_task_events(task_id: str, request: Request) -> list[dict[str, Any]]:
    task = await get_container(request).task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    event_sources = [
        ("task.created", task.created_at),
        ("task.queued", task.queued_at),
        ("task.scheduled", task.scheduled_at),
        ("task.preparing", task.preparing_at),
        ("task.sandbox_starting", task.sandbox_started_at),
        ("task.running", task.started_at),
        ("task.verifying", task.verifying_at),
    ]
    events = [
        {"type": event_type, "task_id": task.id, "at": occurred_at.isoformat()}
        for event_type, occurred_at in event_sources
        if occurred_at is not None
    ]
    if task.completed_at is not None:
        events.append(
            {
                "type": f"task.{task.status}",
                "task_id": task.id,
                "at": task.completed_at.isoformat(),
            }
        )
    return events
