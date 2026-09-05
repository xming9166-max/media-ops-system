"""应用工厂函数。

统一装配 FastAPI 应用：日志、lifespan、中间件、异常处理器、路由。
业务路由通过 ``app.core.modules`` 自动发现，新增模块无需修改本文件。
"""

import re

from fastapi import FastAPI

from app.core.config import settings
from app.core.handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import get_banner_logger, sanitize, setup_logging
from app.core.middleware import register_middleware
from app.core.modules import import_module_routers

banner = get_banner_logger()

# 匹配 DSN/URL 中的密码段：scheme://user:password@host → 保留 scheme/user，掩码 password
_DSN_PASSWORD_RE = re.compile(r"(://[^:/@\s]+:)([^@\s]+)(@)")


def create_app() -> FastAPI:
    """创建并装配 FastAPI 应用实例。"""
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        docs_url=settings.api_docs_url,
        lifespan=lifespan,
    )

    register_middleware(app)
    register_exception_handlers(app)

    # 自动发现业务模块路由，统一挂载 /api/v1 前缀
    for router in import_module_routers():
        app.include_router(router, prefix=settings.api_v1_prefix)

    _print_startup_banner(app)

    return app


def _collect_api_paths(app: FastAPI) -> list[str]:
    """从 OpenAPI schema 收集全部 API 路径（公开 API，含版本前缀，反映真实可访问路由）。"""
    schema = app.openapi()
    return sorted(schema.get("paths", {}).keys())


def _mask_dsn(value: str) -> str:
    """对 DSN / URL 中的密码段脱敏：``mysql+pymysql://root:root@...`` → ``mysql+pymysql://root:***@...``。"""
    return _DSN_PASSWORD_RE.sub(r"\1***\3", value)


def _print_startup_banner(app: FastAPI) -> None:
    """启动横幅：仅打印启动所需信息，供控制台人工阅读。

    使用独立的 banner logger（人类可读格式，不写文件、不影响业务 JSON 日志）。
    配置信息仅在 ``LOG_STARTUP_CONFIG=true`` 时脱敏后输出。
    """
    paths = _collect_api_paths(app)
    banner.info("======服务启动成功======")
    banner.info("监听地址：http://%s:%s", settings.server_host, settings.server_port)
    banner.info(
        "文档地址：http://%s:%s%s",
        settings.server_host,
        settings.server_port,
        settings.api_docs_url,
    )
    banner.info("已注册路由（%d 条）：%s", len(paths), ", ".join(paths))

    if settings.log_startup_config:
        _print_config()


def _print_config() -> None:
    """打印脱敏后的全部配置，供人工核对（仅 LOG_STARTUP_CONFIG=true 时调用）。"""
    banner.info("已加载配置：")
    for key, value in sanitize(settings.model_dump()).items():
        if isinstance(value, str) and "://" in value:
            value = _mask_dsn(value)
        banner.info("  %s = %s", key, value)
