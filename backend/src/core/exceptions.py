from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import logging
import traceback
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 500, details: Dict[str, Any] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=404,
            details={"resource": resource, "identifier": identifier}
        )


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message=message, status_code=401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message=message, status_code=403)


class ValidationError(AppException):
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message=message, status_code=422, details=details)


class ExternalServiceError(AppException):
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} error: {message}",
            status_code=503,
            details={"service": service}
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(f"AppException: {exc.message}", extra={"details": exc.details, "path": request.url.path})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "details": exc.details,
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(f"HTTPException: {exc.detail}", extra={"status_code": exc.status_code, "path": request.url.path})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    logger.warning(f"ValidationError: {exc.errors()}", extra={"path": request.url.path})
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "details": exc.errors()
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        f"Unhandled exception: {exc}",
        extra={
            "path": request.url.path,
            "traceback": traceback.format_exc()
        }
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )


def register_exception_handlers(app):
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)