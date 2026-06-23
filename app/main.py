from __future__ import annotations

from fastapi import FastAPI

from app.api.artifact_api import router as artifact_router
from app.api.callback_api import router as callback_router
from app.api.conversation_ws import router as conversation_router
from app.api.task_api import router as task_router
from app.bootstrap.lifecycle import create_lifespan
from app.config.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=create_lifespan(settings),
    )
    app.include_router(task_router)
    app.include_router(artifact_router)
    app.include_router(conversation_router)
    app.include_router(callback_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
