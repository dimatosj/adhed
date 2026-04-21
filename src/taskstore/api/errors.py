"""Uniform error envelope via FastAPI exception handlers.

Every response — success or failure — has the same top-level shape:
``{"data": ..., "meta": ..., "errors": [...], "warnings": []}``.
Clients can parse one shape for everything.

This also keeps internal schema names and enum member paths out of
error messages surfaced to clients (see taskstore/services/*).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from taskstore.rules.evaluator import RuleEvaluationError, RuleRejection
from taskstore.schemas.common import Envelope, ErrorDetail

logger = logging.getLogger(__name__)


def _envelope_response(errors: list[ErrorDetail], status: int) -> JSONResponse:
    return JSONResponse(
        Envelope(errors=errors).model_dump(mode="json"),
        status_code=status,
    )


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # Some callers already raise with a dict shaped like {"errors": [...]}.
    # That path is now legacy (kept for one release while services migrate);
    # prefer raising RuleRejection / RuleEvaluationError directly.
    if isinstance(exc.detail, dict) and "errors" in exc.detail:
        return JSONResponse(exc.detail, status_code=exc.status_code)
    return _envelope_response(
        errors=[ErrorDetail(message=str(exc.detail))],
        status=exc.status_code,
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Pydantic errors() returns a list of dicts describing each failure.
    # We surface a compact human-readable message per error.
    errors: list[ErrorDetail] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", [])[1:]) or "body"
        msg = err.get("msg", "validation error")
        errors.append(ErrorDetail(message=f"{loc}: {msg}"))
    if not errors:
        errors = [ErrorDetail(message="validation error")]
    return _envelope_response(errors=errors, status=422)


async def _rule_rejection_handler(request: Request, exc: RuleRejection) -> JSONResponse:
    return _envelope_response(
        errors=[ErrorDetail(
            rule_id=str(exc.rule_id),
            rule_name=exc.rule_name,
            message=exc.message,
        )],
        status=422,
    )


async def _rule_evaluation_error_handler(
    request: Request, exc: RuleEvaluationError
) -> JSONResponse:
    logger.warning(
        "rule_evaluation_error_surfaced",
        extra={"rule_id": str(exc.rule_id), "rule_name": exc.rule_name},
    )
    return _envelope_response(
        errors=[ErrorDetail(
            rule_id=str(exc.rule_id),
            rule_name=exc.rule_name,
            message=exc.message,
        )],
        status=422,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(RuleRejection, _rule_rejection_handler)
    app.add_exception_handler(RuleEvaluationError, _rule_evaluation_error_handler)
