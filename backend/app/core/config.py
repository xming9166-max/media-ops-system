import os
from enum import StrEnum

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
        extra="ignore",
    )

    # 运行环境：dev / test / pro
    app_env: AppEnv = AppEnv.DEV

    app_name: str = "media-ops-system"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # 开发环境前端来源，跨域访问由 CORSMiddleware 控制
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


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
