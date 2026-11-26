import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.lifespan import lifespan
from app.schemas.common import ErrorDetail, ErrorResponse, HealthResponse

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(
                code=exc.error_code,
                message=exc.message,
                details=exc.details,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(
                code="validation_error",
                message="Request validation failed.",
                details={"errors": exc.errors()},
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @application.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled internal server error", exc_info=exc)
        body = ErrorResponse(
            error=ErrorDetail(
                code="internal_server_error",
                message="An unexpected internal error occurred.",
            )
        )
        return JSONResponse(status_code=500, content=body.model_dump())

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check(request: Request) -> HealthResponse:
        app_settings = getattr(request.app.state, "settings", settings)
        gemini_ready = getattr(request.app.state, "gemini_client", None) is not None
        return HealthResponse(
            status="ok",
            app_name=app_settings.app_name,
            version=app_settings.app_version,
            gemini_client_ready=gemini_ready,
        )

    application.include_router(v1_router, prefix="/api/v1")
    return application


app = create_app()
