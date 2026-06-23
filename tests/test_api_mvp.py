from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.domain.task import Task, TaskRequest, TaskStatus
from app.main import create_app


def test_task_api_runs_mvp_flow_and_returns_artifact(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            workspace_root=tmp_path / "workspaces",
            task_worker_poll_interval_seconds=0.01,
        )
    )
    with TestClient(app) as client:
        created = client.post(
            "/tasks",
            json={"prompt": "Create a short MVP report.", "allow_write": False},
        )

        assert created.status_code == 200
        body = created.json()
        assert body["status"] in {"queued", "leased", "running", "succeeded"}
        assert body["created_at"]
        assert body["updated_at"]
        task_id = body["task_id"]

        result_body = _wait_for_result(client, task_id)
        assert result_body["status"] == "succeeded"
        assert result_body["summary"]
        assert result_body["artifact_paths"] == ["report.md"]

        artifacts = client.get(f"/tasks/{task_id}/artifacts")
        assert artifacts.status_code == 200
        assert artifacts.json()["artifacts"] == ["report.md"]

        artifact = client.get(f"/tasks/{task_id}/artifacts/report.md")
        assert artifact.status_code == 200
        assert "# MVP Task Report" in artifact.text
        assert "Create a short MVP report." in artifact.text

        events = client.get(f"/tasks/{task_id}/events")
        assert events.status_code == 200
        event_types = [item["type"] for item in events.json()]
        assert "task.created" in event_types
        assert "task.queued" in event_types
        assert "task.scheduled" in event_types
        assert "task.preparing" in event_types
        assert "task.running" in event_types
        assert "task.verifying" in event_types
        assert "task.succeeded" in event_types


def test_task_events_include_full_lifecycle_timestamps(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            workspace_root=tmp_path / "workspaces",
            task_worker_enabled=False,
        )
    )
    now = datetime.now(timezone.utc)
    task = Task.create(TaskRequest(prompt="event test"), task_id="event-task")
    task = task.with_updates(
        status=TaskStatus.SUCCEEDED,
        queued_at=now + timedelta(seconds=1),
        scheduled_at=now + timedelta(seconds=2),
        preparing_at=now + timedelta(seconds=3),
        sandbox_started_at=now + timedelta(seconds=4),
        started_at=now + timedelta(seconds=5),
        verifying_at=now + timedelta(seconds=6),
        completed_at=now + timedelta(seconds=7),
    )

    with TestClient(app) as client:
        import asyncio

        asyncio.run(app.state.container.task_store.create(task))
        response = client.get("/tasks/event-task/events")

        assert response.status_code == 200
        assert [item["type"] for item in response.json()] == [
            "task.created",
            "task.queued",
            "task.scheduled",
            "task.preparing",
            "task.sandbox_starting",
            "task.running",
            "task.verifying",
            "task.succeeded",
        ]


def test_task_api_returns_404_for_missing_task() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/tasks/missing/result")

        assert response.status_code == 404


def test_task_api_accepts_priority(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            workspace_root=tmp_path / "workspaces",
            task_worker_enabled=False,
        )
    )
    with TestClient(app) as client:
        created = client.post(
            "/tasks",
            json={"prompt": "priority task", "priority": 42},
        )

        assert created.status_code == 200
        task_id = created.json()["task_id"]
        import asyncio

        task = asyncio.run(app.state.container.task_store.require(task_id))
        assert task.request.priority == 42


def _wait_for_result(client: TestClient, task_id: str, timeout_seconds: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_body = {}
    while time.monotonic() < deadline:
        result = client.get(f"/tasks/{task_id}/result")
        assert result.status_code == 200
        last_body = result.json()
        if last_body["status"] in {"succeeded", "failed", "cancelled"}:
            return last_body
        time.sleep(0.02)
    raise AssertionError(f"Task did not finish in time: {last_body}")
