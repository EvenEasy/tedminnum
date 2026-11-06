from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ted.domain.rules import Problem
from ted.infrastructure.database import engine
from ted.infrastructure.runtime import settings
from ted.presentation.dependencies import DbSession
from ted.presentation.routers import (
    billing,
    dashboard,
    identity,
    integrations,
    tracking,
    work,
)
from ted.presentation.routers import (
    settings as workspace_settings,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Tedminnum API",
    lifespan=lifespan,
    version="1.0.0",
    docs_url=None,
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.exception_handler(Problem)
async def problem_handler(request: Request, error: Problem) -> JSONResponse:
    return JSONResponse({"detail": error.message}, status_code=error.status)


@app.exception_handler(IntegrityError)
async def conflict_handler(request: Request, error: IntegrityError) -> JSONResponse:
    return JSONResponse({"detail": "Conflicting change; refresh and try again"}, status_code=409)


@app.middleware("http")
async def headers_and_origin(request: Request, call_next: Any) -> Response:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin is not None and not settings.accepts_origin(origin):
            return JSONResponse({"detail": "Origin rejected"}, status_code=403)
    response: Response = await call_next(request)
    if actor_id := getattr(request.state, "actor_id", None):
        response.headers["X-Ted-User-ID"] = actor_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
async def health(db: DbSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/docs", include_in_schema=False)
async def api_docs() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tedminnum API</title><link rel="stylesheet" href="/docs-assets/swagger-ui.css"></head><body><div id="swagger-ui"></div><script src="/docs-assets/swagger-ui-bundle.js"></script><script src="/docs-assets/init.js"></script></body></html>"""
    )


for router in [
    identity.router,
    work.router,
    tracking.router,
    billing.router,
    dashboard.router,
    workspace_settings.router,
    integrations.router,
]:
    app.include_router(router)

# API routes are registered before the SPA fallback.
static = Path(__file__).resolve().parents[4] / "frontend" / "dist"
if static.is_dir():

    class SPA(StaticFiles):
        async def get_response(self, path: str, scope: Any) -> Response:
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            try:
                return await super().get_response(path, scope)
            except Exception as error:
                if getattr(error, "status_code", None) != 404:
                    raise
                return await super().get_response("index.html", scope)

    app.mount("/", SPA(directory=static, html=True), name="web")
