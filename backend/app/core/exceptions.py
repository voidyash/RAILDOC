import logging
import math
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

logger = logging.getLogger("error")


def _sanitize_json(obj):
    """Make a payload strictly JSON-encodable: replace non-finite floats
    with strings and stringify anything exotic (pydantic v2 embeds raw
    ValueError objects in error['ctx'] for some constraint failures).
    """
    if isinstance(obj, float) and not math.isfinite(obj):
        return "NaN" if math.isnan(obj) else ("Infinity" if obj > 0 else "-Infinity")
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_json(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    return str(obj)


def create_error_response(
    status_code: int,
    message: str,
    detail: Optional[str] = None,
    error_code: Optional[str] = None
) -> JSONResponse:
    content = {
        "error": True,
        "message": message,
        "status_code": status_code,
        # `detail` mirrors FastAPI's default shape — the frontend reads
        # response.data.detail on failures.
        "detail": message,
    }
    if detail:
        content["detail"] = detail
    if error_code:
        content["error_code"] = error_code
    return JSONResponse(status_code=status_code, content=content)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - Path: {request.url.path}")
    return create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code="HTTP_ERROR"
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Request-body validation failures (422).

    Overrides FastAPI's default handler, which embeds the raw offending
    input in the error body: a NaN/Infinity literal is correctly rejected
    by the model (allow_inf_nan=False), but then CRASHES the response
    encoding itself (Starlette dumps with allow_nan=False), turning a
    proper 422 into an unserializable 500. Sanitize the payload instead.
    """
    errors = _sanitize_json(exc.errors())
    logger.warning(f"Validation error: {errors} - Path: {request.url.path}")
    return JSONResponse(status_code=422, content={"detail": errors})


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    logger.warning(f"Validation error: {errors} - Path: {request.url.path}")
    return create_error_response(
        status_code=422,
        message="Validation failed",
        detail=str(errors),
        error_code="VALIDATION_ERROR"
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc} - Path: {request.url.path}",
        exc_info=True
    )
    return create_error_response(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        message="An internal error occurred",
        error_code="INTERNAL_ERROR"
    )


def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)