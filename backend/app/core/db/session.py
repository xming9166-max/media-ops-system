"""数据库会话工厂与 FastAPI 依赖.

设计要点:
- engine 懒初始化:mysql_dsn 为空则返回 None,服务可无库启动.
- pool_pre_ping=True 防断线僵尸连接.
- get_session 为每请求建立 Session,结束时 close;提交由 Service 显式控制.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine | None:
    """按 mysql_dsn 建立 engine 单例.未配置 DSN 时返回 None."""
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine
    if not settings.mysql_dsn:
        return None
    _engine = create_engine(
        settings.mysql_dsn,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        echo=settings.db_echo,
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖:每请求一个 Session,结束统一 close.

    提交/回滚由 Service 在事务边界显式调用,本依赖只负责生命周期.
    """
    if _SessionLocal is None:
        # 未配置数据库时 yield 一个占位,调用方若真用会报错.
        yield None  # type: ignore[misc]
        return
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
