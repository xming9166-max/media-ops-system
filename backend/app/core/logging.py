"""日志基础设施：统一 JSON Schema、上下文、脱敏、输出装配。

提供能力：

- 统一结构化 JSON 日志（单行输出，字段恒定，可直接对接
      Loki / ELK / Grafana / OpenTelemetry）
- 公共字段：timestamp level logger log_type app_name app_env trace_id request_id
  task_id user_id message
- 三类日志按 ``log_type`` 区分（access / app / error），logger 名与 log_type 解耦
- 敏感信息脱敏（基础设施层集中处理，业务代码无需关心）
- 输出位置：console / file / both；文件按类型分三个，ERROR+ 跨类型统一入 error.log

使用方式::

    from app.core.logging import get_app_logger

    logger = get_app_logger(__name__)
    logger.info(
        "文章创建成功",
        extra={"action": "create", "entity_type": "article", "success": True},
    )
"""

import json
import logging
import logging.handlers
import re
from datetime import UTC, datetime
from typing import Any

from app.core.config import LogLevel, LogOutput, settings
from app.core.log_context import get_task_id, get_trace_id, get_user_id
from app.core.request_id import get_request_id

# ---- 日志类型常量 ----
LOG_TYPE_ACCESS = "access"
LOG_TYPE_APP = "app"
LOG_TYPE_ERROR = "error"

# ---- 脱敏：键名（大小写不敏感、含子串即命中）----
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "api_key",
        "apikey",
        "secret",
        "client_secret",
        "credential",
    }
)

# ---- 脱敏：值形态正则 ----
# 中国大陆身份证号（18 位，末位可为 X）
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{6})(\d{8})(\d{3}[\dXx])(?!\d)")
# 中国大陆手机号（11 位，1[3-9] 开头）
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
# 银行卡号（13~19 位连续数字）
_BANK_RE = re.compile(r"(?<!\d)(\d{6})(\d{6,13})(\d{4})(?!\d)")
# 邮箱
_EMAIL_RE = re.compile(r"\b([\w.+-])([\w.+-]*)(@[\w-]+(?:\.[\w-]+)+)\b")

# LogRecord 标准属性集合（用于从 record 中区分自定义字段）
_STANDARD_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


def _is_sensitive_key(key: str) -> bool:
    """判断键名是否敏感（大小写不敏感、短横线转下划线、子串命中）。"""
    normalized = key.lower().replace("-", "_")
    return any(sensitive in normalized for sensitive in _SENSITIVE_KEYS)


def _mask_value(value: str) -> str:
    """对字符串值做形态脱敏（身份证 / 手机号 / 银行卡 / 邮箱）。"""
    value = _ID_CARD_RE.sub(lambda m: f"{m.group(1)}********{m.group(3)}", value)
    value = _PHONE_RE.sub(lambda m: f"{m.group(1)}****{m.group(3)}", value)
    value = _BANK_RE.sub(lambda m: f"{m.group(1)}******{m.group(3)}", value)
    value = _EMAIL_RE.sub(lambda m: f"{m.group(1)}***{m.group(3)}", value)
    return value


def sanitize(data: Any) -> Any:
    """递归脱敏：敏感键整体置 ``"***"``，字符串值做形态脱敏。

    集中在日志基础设施层，业务代码无需自行处理。
    """
    if isinstance(data, dict):
        return {k: "***" if _is_sensitive_key(k) else sanitize(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [sanitize(item) for item in data]
    if isinstance(data, str):
        return _mask_value(data)
    return data


class JsonFormatter(logging.Formatter):
    """统一结构化 JSON 格式器（单行输出）。

    共字段恒定输出，自定义字段（由 ``extra`` 注入）递归脱敏后以平铺方式写入。
    若存在未处理异常，追加 ``traceback`` 字段。
    """

    def __init__(self, app_name: str, app_env: str) -> None:
        super().__init__()
        self._app_name = app_name
        self._app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "log_type": getattr(record, "log_type", ""),
            "app_name": self._app_name,
            "app_env": self._app_env,
            "trace_id": get_trace_id() or get_request_id(),
            "request_id": get_request_id(),
            "task_id": get_task_id(),
            "user_id": get_user_id(),
            "message": record.getMessage(),
        }

        # 收集自定义字段（跳过 LogRecord 标准属性 / 私有属性）并脱敏
        extras: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_KEYS or key.startswith("_"):
                continue
            extras[key] = value
        if extras:
            entry.update(sanitize(extras))

        # 异常堆栈（脱敏后写入，防止异常信息泄露敏感数据）
        if record.exc_info and record.exc_info[0] is not None:
            entry["traceback"] = _mask_value(self.formatException(record.exc_info))

        return json.dumps(entry, ensure_ascii=False, default=str)


class TypeFilter(logging.Filter):
    """按 ``log_type`` 字段路由（用于 access.log / app.log）。"""

    def __init__(self, log_type: str) -> None:
        super().__init__()
        self._log_type = log_type

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "log_type", "") == self._log_type


class MaxLevelFilter(logging.Filter):
    """仅放行严格低于 ``max_level`` 的记录（用于 access.log / app.log 排除 ERROR+）。"""

    def __init__(self, max_level: int) -> None:
        super().__init__()
        self._max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self._max_level


class MinLevelFilter(logging.Filter):
    """仅放行不低于 ``min_level`` 的记录（用于 error.log）。"""

    def __init__(self, min_level: int) -> None:
        super().__init__()
        self._min_level = min_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self._min_level


def _level_from_settings(level: LogLevel) -> int:
    """将配置级别转为 logging 级别整数。"""
    resolved = logging.getLevelName(level.value)
    if isinstance(resolved, int):
        return resolved
    return logging.INFO


def setup_logging() -> None:
    """装配日志系统（幂等，应用启动时调用一次）。

    - ``LOG_ENABLED=false``：项目根 logger ``app`` 挂 NullHandler + propagate=False，
      不输出、保留 logger 调用能力、不动全局 logging、不影响第三方库日志。
    - console：单行 JSON，按级别过滤，三类日志全收。
    - file：三个轮转文件（10MB × 5），按 ``log_type`` 路由；ERROR+ 跨类型统一入 error.log。
    """
    effective_level = _level_from_settings(settings.log_level)

    # 项目根 logger（所有 app.* 自然落入）
    app_logger = logging.getLogger("app")
    app_logger.setLevel(effective_level)
    app_logger.propagate = False

    # 清除旧 handler，保证幂等
    for handler in app_logger.handlers[:]:
        app_logger.removeHandler(handler)

    if not settings.log_enabled:
        # 不输出但保留调用能力；不调用 logging.disable()
        app_logger.addHandler(logging.NullHandler())
        return

    formatter = JsonFormatter(app_name=settings.app_name, app_env=settings.app_env.value)
    use_console = settings.log_output in (LogOutput.CONSOLE, LogOutput.BOTH)
    use_file = settings.log_output in (LogOutput.FILE, LogOutput.BOTH)

    if use_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(effective_level)
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)

    if use_file:
        import os

        os.makedirs(settings.log_dir, exist_ok=True)

        # access.log：log_type=access，级别 [effective, ERROR)
        access_handler = logging.handlers.RotatingFileHandler(
            filename=f"{settings.log_dir}/access.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        access_handler.setLevel(effective_level)
        access_handler.setFormatter(formatter)
        access_handler.addFilter(TypeFilter(LOG_TYPE_ACCESS))
        access_handler.addFilter(MaxLevelFilter(logging.ERROR))

        # app.log：log_type=app，级别 [effective, ERROR)
        app_file_handler = logging.handlers.RotatingFileHandler(
            filename=f"{settings.log_dir}/app.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        app_file_handler.setLevel(effective_level)
        app_file_handler.setFormatter(formatter)
        app_file_handler.addFilter(TypeFilter(LOG_TYPE_APP))
        app_file_handler.addFilter(MaxLevelFilter(logging.ERROR))

        # error.log：任意 log_type，级别 >= ERROR（含完整堆栈）
        error_handler = logging.handlers.RotatingFileHandler(
            filename=f"{settings.log_dir}/error.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)

        app_logger.addHandler(access_handler)
        app_logger.addHandler(app_file_handler)
        app_logger.addHandler(error_handler)


class _ContextLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter 子类：合并上下文 ``extra`` 与调用者传入的 ``extra``。

    标准 ``LoggerAdapter.process`` 会直接覆盖 ``kwargs["extra"]`` 导致调用者
    传入的 ``extra``(如 access 日志的 method/path/status、业务日志的 action/...) 丢失。
    此处改为合并,保留上下文注入的 ``log_type`` 同时不丢弃业务字段。
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        kwargs["extra"] = {**self.extra, **kwargs.get("extra", {})}
        return msg, kwargs


def _wrap_logger(name: str, log_type: str) -> _ContextLoggerAdapter:
    """用 LoggerAdapter 注入 ``log_type``，logger 名保持 __name__（与类型解耦）。"""
    logger = logging.getLogger(name)
    return _ContextLoggerAdapter(logger, {"log_type": log_type})


def get_app_logger(name: str) -> logging.LoggerAdapter:
    """业务 / 应用日志（INFO / WARNING）。::

    logger = get_app_logger(__name__)
    logger.info("创建成功", extra={"action": "create", "success": True})
    """
    return _wrap_logger(name, LOG_TYPE_APP)


def get_error_logger(name: str) -> logging.LoggerAdapter:
    """错误日志（ERROR / CRITICAL，含完整堆栈）。"""
    return _wrap_logger(name, LOG_TYPE_ERROR)


def get_access_logger(name: str) -> logging.LoggerAdapter:
    """访问日志（通常由 AccessLogMiddleware 使用）。"""
    return _wrap_logger(name, LOG_TYPE_ACCESS)


def get_banner_logger() -> logging.Logger:
    """启动横幅 logger：人类可读、独立于结构化 JSON 日志。

    仅用于启动信息展示（应用启动横幅）。特性：

    - 自定义简洁格式 ``[INFO] 消息``，不输出 JSON 公共字段；
    - ``propagate=False``，不传播到 ``app`` 根 logger，完全不影响业务 JSON 日志；
    - 只挂 console handler，不写文件，不污染 ``backend/logs/*``。

    factory.py 启动时调用，输出应用名 / 监听地址 / 文档地址等一次性信息。
    """
    logger = logging.getLogger("app.banner")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if not logger.handlers:  # 幂等：避免重复挂 handler
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


__all__: list[str] = [
    "LOG_TYPE_ACCESS",
    "LOG_TYPE_APP",
    "LOG_TYPE_ERROR",
    "sanitize",
    "JsonFormatter",
    "TypeFilter",
    "MaxLevelFilter",
    "MinLevelFilter",
    "setup_logging",
    "get_app_logger",
    "get_error_logger",
    "get_access_logger",
    "get_banner_logger",
]
