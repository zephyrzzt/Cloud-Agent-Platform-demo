from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.bootstrap.container import create_container
from app.config.settings import Settings


def create_lifespan(settings: Settings | None = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = create_container(settings=settings)
        app.state.container = container
        app.state.worker_task = None

        if container.settings.task_worker_enabled:
            app.state.worker_task = asyncio.create_task(container.worker.run_forever())

        try:
            yield
        finally:
            container.worker.stop()
            worker_task = app.state.worker_task
            if worker_task is not None:
                worker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await worker_task

    return lifespan


lifespan = create_lifespan()
