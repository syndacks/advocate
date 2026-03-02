"""FastAPI application entrypoint.

Phase 0: minimal health endpoint only.
Subsequent phases add ingestion, state, and rendering routers.
"""

from fastapi import FastAPI

from advocate.config import settings

app = FastAPI(
    title="Advocate",
    description="Local job-search case engine",
    version=settings.app_version,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
