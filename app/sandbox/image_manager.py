from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.sandbox.errors import SandboxStartError


@dataclass(frozen=True)
class SandboxImageManager:
    docker_binary: str = "docker"

    def build_command(
        self,
        *,
        image: str,
        dockerfile: str | Path = "sandbox/Dockerfile",
        context: str | Path = "sandbox",
    ) -> list[str]:
        return [
            self.docker_binary,
            "build",
            "-t",
            image,
            "-f",
            str(dockerfile),
            str(context),
        ]

    async def build_image(
        self,
        *,
        image: str,
        dockerfile: str | Path = "sandbox/Dockerfile",
        context: str | Path = "sandbox",
    ) -> subprocess.CompletedProcess[str]:
        try:
            return await asyncio.to_thread(
                subprocess.run,
                self.build_command(
                    image=image,
                    dockerfile=dockerfile,
                    context=context,
                ),
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise SandboxStartError("docker executable was not found") from exc

    async def image_exists(self, image: str) -> bool:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [self.docker_binary, "image", "inspect", image],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise SandboxStartError("docker executable was not found") from exc
        return result.returncode == 0
