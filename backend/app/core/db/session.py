"""数据库会话工厂与 FastAPI 依赖.

设计要点:
- engine 懒初始化:mysql_dsn 为空则返回 None,服务可无库启动.
- pool_pre_ping=True 防断线僵尸连接.
- get_session 为每请求建立 Session,结束时 close;提交由 Service 显式控制.
- 当前请求 Session 存入 contextvar(单请求单 Session 约定),
  Repository 可通过 get_current_session() 缺省取用,无需显式传递.
"""

from collections.abc import Generator
from contextvars import ContextVar, Token

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None

# 当前请求的 Session(单请求单 Session 约定).
# 与 request_id 同构的 contextvar 模式:依赖进入时 set,退出时 reset.
_session_var: ContextVar[Session | None] = ContextVar("db_session", default=None)


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


def dispose_engine() -> None:
    """释放 engine 单例与对应 SessionLocal.

    应用关闭时调用;未初始化 engine 时 no-op.
    """
    global _engine, _SessionLocal
    if _engine is None:
        return
    _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_current_session() -> Session | None:
    """读取当前请求上下文中的 Session.

    请求链路内(经过 get_session 依赖)返回该 Session;
    非请求上下文(脚本/测试/Celery)返回 None.
    """
    return _session_var.get()


def resolve_session(session: Session | None = None) -> Session:
    """解析可用 Session:显式传入优先,否则取请求上下文.

    两者皆无时抛出明确错误,避免 Repository 后续出现不可读的 AttributeError.
    """
    resolved = session or get_current_session()
    if resolved is None:
        raise RuntimeError(
            "无可用数据库 Session:请显式传入 session,或在请求上下文(get_session 依赖)内使用"
        )
    return resolved


def get_session(request: Request) -> Generator[Session, None, None]:
    """FastAPI 依赖:每请求一个 Session,结束统一 close.

    写入两处(单请求单 Session 约定):
    - contextvar:供请求链路内 Repository 缺省取用(get_current_session).
    - request.state.db_session:供 CommitMiddleware 兜底读取——
      BaseHTTPMiddleware 的 call_next 在独立 task 中运行,依赖内 set 的
      contextvar 不会传播回中间件,必须经 scope 共享的 request.state.

    退出时 reset + close.提交/回滚由 Service 显式调用或中间件兜底.
    """
    if _SessionLocal is None:
        # 未配置数据库时 yield 一个占位,调用方若真用会报错.
        yield None  # type: ignore[misc]
        return
    session = _SessionLocal()
    token: Token[Session | None] = _session_var.set(session)
    request.state.db_session = session
    try:
        yield session
    finally:
        _session_var.reset(token)
        session.close()
