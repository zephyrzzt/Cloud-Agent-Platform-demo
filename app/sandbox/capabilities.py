from __future__ import annotations

from enum import StrEnum


class SandboxCapability(StrEnum):
    EXEC = "exec"
    PAUSE_RESUME = "pause_resume"
    NETWORK_CONTROL = "network_control"
    READ_ONLY_ROOT = "read_only_root"
    RESOURCE_LIMITS = "resource_limits"
    SNAPSHOT = "snapshot"
    EXPOSE_PORT = "expose_port"
    FILE_TRANSFER = "file_transfer"
