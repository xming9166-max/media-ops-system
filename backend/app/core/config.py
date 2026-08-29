from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "media-ops-system"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # 开发环境前端来源，跨域访问由 CORSMiddleware 控制
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
