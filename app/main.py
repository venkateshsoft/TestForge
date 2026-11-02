from __future__ import annotations

import io
import logging
import os
import time
import zipfile
from collections import defaultdict, deque
from pathlib import Path, PurePosixPath
from uuid import UUID

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import settings
from .generator import generate
from .models import GenerationResponse, ScenarioRequest
from .store import get, list_all, save
from .validation import validate

logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("testforge")


class RequestGuardMiddleware(BaseHTTPMiddleware):
    """Small single-process guardrail; use an edge proxy for distributed rate limiting."""

    def __init__(self, app):
        super().__init__(app)
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or os.urandom(8).hex()
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > settings.max_request_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request body too large", "request_id": request_id}, headers={"x-request-id": request_id})
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self.requests[client]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= settings.rate_limit_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded", "request_id": request_id}, headers={"retry-after": "60", "x-request-id": request_id})
        window.append(now)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        logger.info("%s %s %s %.3fs request_id=%s", request.method, request.url.path, response.status_code, time.perf_counter() - started, request_id)
        return response


app = FastAPI(title="TestForge AI", version="0.1.0", description="From Plain English to Reliable Automated Testing")
app.add_middleware(RequestGuardMiddleware)
if settings.allowed_hosts and settings.allowed_hosts != ("*",):
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors()), "request_id": getattr(request.state, "request_id", None)})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "request_id": getattr(request.state, "request_id", None)})


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "testforge-api"}


@app.post("/api/v1/generations", response_model=GenerationResponse, status_code=201)
def create_generation(request: ScenarioRequest) -> GenerationResponse:
    generation = generate(request)
    save(generation)
    return GenerationResponse(**generation.model_dump())


@app.get("/api/v1/generations/{generation_id}", response_model=GenerationResponse)
def get_generation(generation_id: UUID) -> GenerationResponse:
    generation = get(generation_id)
    if not generation:
        raise HTTPException(404, "Generation not found")
    return GenerationResponse(**generation.model_dump())


@app.get("/api/v1/projects", response_model=list[GenerationResponse])
def projects() -> list[GenerationResponse]:
    return [GenerationResponse(**item.model_dump()) for item in list_all()]


@app.post("/api/v1/projects/{generation_id}/validate", response_model=GenerationResponse)
def validate_generation(generation_id: UUID) -> GenerationResponse:
    generation = get(generation_id)
    if not generation:
        raise HTTPException(404, "Project not found")
    generation.validation = validate(generation.files)
    save(generation)
    return GenerationResponse(**generation.model_dump())


@app.get("/api/v1/projects/{generation_id}/download")
def download_generation(generation_id: UUID) -> StreamingResponse:
    generation = get(generation_id)
    if not generation:
        raise HTTPException(404, "Project not found")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in generation.files:
            path = PurePosixPath(file.path)
            if path.is_absolute() or ".." in path.parts or "\\" in file.path:
                raise HTTPException(500, "Unsafe generated path")
            bundle.writestr(f"testforge-project/{path.as_posix()}", file.content)
    archive.seek(0)
    return StreamingResponse(archive, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="testforge-{generation_id}.zip"'})


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, log_level=settings.log_level.lower())
