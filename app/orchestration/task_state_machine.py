from __future__ import annotations

from datetime import datetime, timezone

from app.domain.task import Task, TaskResult, TaskStatus
from app.orchestration.errors import InvalidTaskTransitionError


class TaskStateMachine:
    VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.CREATED: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
        TaskStatus.QUEUED: {TaskStatus.LEASED, TaskStatus.CANCELLED},
        TaskStatus.LEASED: {
            TaskStatus.SCHEDULED,
            TaskStatus.QUEUED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.SCHEDULED: {TaskStatus.PREPARING, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.PREPARING: {
            TaskStatus.SANDBOX_STARTING,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.SANDBOX_STARTING: {
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.RUNNING: {TaskStatus.VERIFYING, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.VERIFYING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.SUCCEEDED: set(),
        TaskStatus.FAILED: set(),
        TaskStatus.CANCELLED: set(),
    }

    def transition(
        self,
        task: Task,
        new_status: TaskStatus,
        *,
        lease_id: str | None = None,
        result: TaskResult | None = None,
        error: str | None = None,
    ) -> Task:
        self.assert_can_transition(task.status, new_status)
        now = datetime.now(timezone.utc)
        changes = {
            "status": new_status,
            "error": error,
        }

        if new_status == TaskStatus.QUEUED:
            changes["queued_at"] = task.queued_at or now
            changes["lease_id"] = None
        elif new_status == TaskStatus.LEASED:
            changes["lease_id"] = lease_id
        elif new_status == TaskStatus.SCHEDULED:
            changes["scheduled_at"] = task.scheduled_at or now
            changes["lease_id"] = lease_id or task.lease_id
        elif new_status == TaskStatus.PREPARING:
            changes["preparing_at"] = task.preparing_at or now
            changes["lease_id"] = lease_id or task.lease_id
        elif new_status == TaskStatus.SANDBOX_STARTING:
            changes["sandbox_started_at"] = task.sandbox_started_at or now
            changes["lease_id"] = lease_id or task.lease_id
        elif new_status == TaskStatus.RUNNING:
            changes["started_at"] = task.started_at or now
            changes["lease_id"] = lease_id or task.lease_id
        elif new_status == TaskStatus.VERIFYING:
            changes["verifying_at"] = task.verifying_at or now
            changes["lease_id"] = lease_id or task.lease_id
        elif new_status in {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            changes["completed_at"] = now
            changes["lease_id"] = None
            changes["result"] = result

        return task.with_updates(**changes)

    def assert_can_transition(
        self,
        current: TaskStatus,
        new_status: TaskStatus,
    ) -> None:
        if new_status not in self.VALID_TRANSITIONS.get(current, set()):
            raise InvalidTaskTransitionError(
                f"Cannot transition task from {current} to {new_status}"
            )
