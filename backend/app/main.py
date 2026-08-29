import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import ApiCode, ApiException
from app.core.middleware import RequestIDMiddleware
from app.core.response import ApiResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(ApiException)
async def api_exception_handler(request: Request, exc: ApiException) -> ApiResponse:
    """业务异常统一转为契约响应。"""
    logger.warning(
        "api error: path=%s code=%s message=%s",
        request.url.path,
        exc.code,
        exc.message,
    )
    return ApiResponse.error(
        http_status=exc.http_status,
        code=exc.code,
        message=exc.message,
        data=exc.data,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> ApiResponse:
    """参数校验失败统一返回 422 / 40000。"""
    logger.warning("validation error: path=%s errors=%s", request.url.path, exc.errors())
    return ApiResponse.error(
        http_status=422,
        code=ApiCode.PARAM_ERROR,
        message="参数错误",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> ApiResponse:
    """未捕获异常统一兜底为 500 / 50000，不向外泄露内部细节。"""
    logger.exception(
        "unhandled exception: %s %s", request.method, request.url.path
    )
    return ApiResponse.error(
        http_status=500,
        code=ApiCode.INTERNAL_ERROR,
        message="服务器内部错误",
    )


@app.get(f"{settings.api_v1_prefix}/health")
async def health_check() -> ApiResponse:
    """Health check endpoint."""
    return ApiResponse.success(data={"status": "ok"})
