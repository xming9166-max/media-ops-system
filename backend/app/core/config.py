import os
from enum import StrEnum

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_VAR_APP_ENV = "APP_ENV"
_ENV_VAR_CONFIG_SOURCE = "CONFIG_SOURCE"


class AppEnv(StrEnum):
    """运行环境。"""

    DEV = "dev"
    TEST = "test"
    PRO = "pro"


class ConfigSource(StrEnum):
    """配置读取方式。"""

    FILE = "file"  # 从 .env.{app_env} 文件读取
    ENV = "env"  # 只从进程环境变量读取


class LogOutput(StrEnum):
    """日志输出位置。"""

    CONSOLE = "console"
    FILE = "file"
    BOTH = "both"


class LogLevel(StrEnum):
    """日志级别（值直接对应 logging 级别名）。"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# 未显式设置 CONFIG_SOURCE 时，按运行环境推断默认读取方式：
# dev → 文件（方便本地开发），test / pro → 环境变量（CI 与生产不依赖文件）
_DEFAULT_SOURCE_BY_ENV: dict[AppEnv, ConfigSource] = {
    AppEnv.DEV: ConfigSource.FILE,
    AppEnv.TEST: ConfigSource.ENV,
    AppEnv.PRO: ConfigSource.ENV,
}


class Settings(BaseSettings):
    """Application configuration loaded from environment or env file."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="forbid",  # 未知键快速失败,
    )

    # 运行环境：dev / test / pro
    app_env: AppEnv = AppEnv.DEV

    app_name: str = "media-ops-system"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # 开发环境前端来源，跨域访问由 CORSMiddleware 控制
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 日志配置
    # 未显式设置时，各键按 app_env 推断默认值（dev/test 偏开发友好，pro 偏生产安全）；
    # 显式设置优先。
    log_enabled: bool = True  # 日志主开关；关闭时项目内 logger 不输出（不改动全局 logging）
    log_output: LogOutput | None = (
        None  # 输出位置：未设置时按 env 推断（dev→console，test/pro→file）
    )
    log_level: LogLevel = LogLevel.INFO  # 日志级别
    log_dir: str = "logs"  # 文件输出目录（相对 backend/ 运行目录），仅 FILE / BOTH 生效
    log_access_body: bool | None = None  # 是否采样请求/响应 Body；未设置时按 env 推断
    log_body_max_bytes: int = 4096  # Body 采样上限（字节），超出截断并打 truncated 标记
    log_slow_request_ms: int = 1000  # 慢请求阈值（毫秒），超时访问日志升 WARNING 并打标；0 关闭
    log_trust_proxy_headers: bool | None = None  # 是否信任代理头取客户端 IP；未设置时按 env 推断

    @model_validator(mode="after")
    def _infer_log_defaults(self) -> "Settings":
        """未显式设置日志键时，按运行环境推断默认值。

        进程环境变量 / 配置文件已显式设置时（字段非 None / 非默认）保持优先；
        推断仅对仍为 None 的开关字段生效。
        """
        if self.log_output is None:
            self.log_output = LogOutput.CONSOLE if self.app_env == AppEnv.DEV else LogOutput.FILE
        if self.log_access_body is None:
            # dev 默认开启 Body 采样便于排查，test / pro 默认关闭避免性能与泄露
            self.log_access_body = self.app_env == AppEnv.DEV
        if self.log_trust_proxy_headers is None:
            # pro 通常部署在反代后，信任 X-Forwarded-For；本地开发直接取 client host
            self.log_trust_proxy_headers = self.app_env == AppEnv.PRO
        return self


def _parse_enum_env[T: StrEnum](var_name: str, raw_value: str, enum_cls: type[T]) -> T:
    """解析枚举型环境变量，非法取值直接报错（快速失败，不静默回退）。"""
    try:
        return enum_cls(raw_value.strip().lower())
    except ValueError:
        valid = ", ".join(member.value for member in enum_cls)
        raise ValueError(
            f"环境变量 {var_name} 取值非法: {raw_value!r}（合法值: {valid}）"
        ) from None


# 环境文件统一放在 env/ 目录下（相对后端运行目录）
_ENV_FILE_DIR = "env"


def _env_file_for(app_env: AppEnv) -> str:
    """文件模式下各环境对应的配置文件路径：``env/.env.{app_env}``。

    - dev  → ``env/.env.dev``
    - test → ``env/.env.test``
    - pro  → ``env/.env.pro``
    """
    return f"{_ENV_FILE_DIR}/.env.{app_env.value}"


def load_settings() -> Settings:
    """按运行环境加载配置。

    - ``APP_ENV``：运行环境（dev / test / pro），缺省 ``dev``；
      文件模式读取 ``env/.env.{APP_ENV}``（如 ``env/.env.dev``）。
    - ``CONFIG_SOURCE``：配置读取方式（file / env）；缺省按环境推断
      （dev → file，test / pro → env），显式设置时优先生效。
    - 取值优先级：进程环境变量 > 配置文件 > 字段默认值。
    """
    raw_app_env = os.getenv(_ENV_VAR_APP_ENV, AppEnv.DEV.value)
    app_env = _parse_enum_env(_ENV_VAR_APP_ENV, raw_app_env, AppEnv)

    raw_source = os.getenv(_ENV_VAR_CONFIG_SOURCE)
    if raw_source is None:
        source = _DEFAULT_SOURCE_BY_ENV[app_env]
    else:
        source = _parse_enum_env(_ENV_VAR_CONFIG_SOURCE, raw_source, ConfigSource)

    env_file = _env_file_for(app_env) if source == ConfigSource.FILE else None
    return Settings(_env_file=env_file, app_env=app_env)


settings = load_settings()
