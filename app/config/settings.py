from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _optional_int_env(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    if value.lower() in {"", "none", "null", "disabled"}:
        return None
    return int(value)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Cloud Agent Platform"
    app_env: str = "development"
    app_version: str = "0.1.0"
    workspace_root: Path = Path(".local/workspaces")
    default_model_provider: str = "mock"
    default_model_name: str = "mock-agent"
    openai_compatible_base_url: str = "https://api.openai.com/v1"
    openai_compatible_api_key: str | None = None
    openai_compatible_timeout_seconds: float = 60.0
    sandbox_provider: str = "disabled"
    sandbox_image: str = "cloud-agent-sandbox:latest"
    sandbox_network: str = "none"
    sandbox_command_timeout_seconds: int = 30
    sandbox_max_output_bytes: int = 20_000
    task_scheduler_max_concurrent_tasks: int | None = None
    task_scheduler_max_sandbox_tasks: int | None = None
    task_worker_enabled: bool = True
    task_worker_poll_interval_seconds: float = 0.05
    task_worker_lease_ttl_seconds: int = 300
    task_worker_lease_heartbeat_interval_seconds: float = 30.0
    task_worker_id: str = "api-worker"
    agent_max_turns: int = 4
    agent_max_tool_calls: int = 8

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", cls.app_name),
            app_env=os.getenv("APP_ENV", cls.app_env),
            app_version=os.getenv("APP_VERSION", cls.app_version),
            workspace_root=Path(os.getenv("WORKSPACE_ROOT", str(cls.workspace_root))),
            default_model_provider=os.getenv(
                "DEFAULT_MODEL_PROVIDER",
                cls.default_model_provider,
            ),
            default_model_name=os.getenv("DEFAULT_MODEL_NAME", cls.default_model_name),
            openai_compatible_base_url=os.getenv(
                "OPENAI_COMPATIBLE_BASE_URL",
                cls.openai_compatible_base_url,
            ),
            openai_compatible_api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY")
            or os.getenv("OPENAI_API_KEY"),
            openai_compatible_timeout_seconds=_float_env(
                "OPENAI_COMPATIBLE_TIMEOUT_SECONDS",
                cls.openai_compatible_timeout_seconds,
            ),
            sandbox_provider=os.getenv("SANDBOX_PROVIDER", cls.sandbox_provider),
            sandbox_image=os.getenv("SANDBOX_IMAGE", cls.sandbox_image),
            sandbox_network=os.getenv("SANDBOX_NETWORK", cls.sandbox_network),
            sandbox_command_timeout_seconds=_int_env(
                "SANDBOX_COMMAND_TIMEOUT_SECONDS",
                cls.sandbox_command_timeout_seconds,
            ),
            sandbox_max_output_bytes=_int_env(
                "SANDBOX_MAX_OUTPUT_BYTES",
                cls.sandbox_max_output_bytes,
            ),
            task_scheduler_max_concurrent_tasks=_optional_int_env(
                "TASK_SCHEDULER_MAX_CONCURRENT_TASKS",
                cls.task_scheduler_max_concurrent_tasks,
            ),
            task_scheduler_max_sandbox_tasks=_optional_int_env(
                "TASK_SCHEDULER_MAX_SANDBOX_TASKS",
                cls.task_scheduler_max_sandbox_tasks,
            ),
            task_worker_enabled=_bool_env(
                "TASK_WORKER_ENABLED",
                cls.task_worker_enabled,
            ),
            task_worker_poll_interval_seconds=_float_env(
                "TASK_WORKER_POLL_INTERVAL_SECONDS",
                cls.task_worker_poll_interval_seconds,
            ),
            task_worker_lease_ttl_seconds=_int_env(
                "TASK_WORKER_LEASE_TTL_SECONDS",
                cls.task_worker_lease_ttl_seconds,
            ),
            task_worker_lease_heartbeat_interval_seconds=_float_env(
                "TASK_WORKER_LEASE_HEARTBEAT_INTERVAL_SECONDS",
                cls.task_worker_lease_heartbeat_interval_seconds,
            ),
            task_worker_id=os.getenv("TASK_WORKER_ID", cls.task_worker_id),
            agent_max_turns=_int_env("AGENT_MAX_TURNS", cls.agent_max_turns),
            agent_max_tool_calls=_int_env(
                "AGENT_MAX_TOOL_CALLS",
                cls.agent_max_tool_calls,
            ),
        )
