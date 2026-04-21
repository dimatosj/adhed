"""Security-adjacent middleware.

- CORS: opt-in via CORS_ORIGINS env (comma-separated list).
- Request body size cap: rejects oversized requests at 413 before
  endpoint logic runs. Caps JSONB bloat and naive DoS attempts at
  the edge.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from taskstore.schemas.common import Envelope, ErrorDetail


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose Content-Length exceeds ``max_bytes``
    with 413. Does NOT attempt to buffer the body to measure streaming
    requests — clients that omit Content-Length on a streaming upload
    will pass through; in practice ADHED only takes JSON bodies and
    httpx/curl set Content-Length for those."""

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > self.max_bytes:
                    return JSONResponse(
                        Envelope(errors=[ErrorDetail(
                            message=f"Request body exceeds {self.max_bytes} byte limit",
                        )]).model_dump(mode="json"),
                        status_code=413,
                    )
            except ValueError:
                # Malformed Content-Length header — let downstream decide.
                pass
        return await call_next(request)


def register_middleware(app: FastAPI) -> None:
    """Wire up all middleware. Order matters: CORS first so preflight
    responses aren't subject to the body-size check."""
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["X-API-Key", "X-User-Id", "Content-Type"],
        )

    try:
        max_bytes = int(os.environ.get("MAX_BODY_BYTES", "1048576"))  # 1 MiB
    except ValueError:
        max_bytes = 1048576
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes)
