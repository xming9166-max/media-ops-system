"""事务辅助:按需提交 / 上下文事务 / 函数级兜底提交.

- commit_or_rollback:提交失败回滚后原样抛出(绝不吞异常).
- transaction:上下文管理器,把多个写操作包成一个原子单元.
- has_pending:判断 Session 是否有未提交变更.
- auto_commit:函数级兜底装饰器(面向 Celery 等非 HTTP 场景;
  FastAPI 走 CommitMiddleware 统一兜底).
"""

import inspect
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

from sqlalchemy.orm import Session

from app.core.db.session import get_current_session


def commit_or_rollback(session: Session) -> None:
    """尝试提交;失败则回滚复位会话并原样抛出(绝不吞异常).

    - 成功:数据落库.
    - 失败:rollback 复位失效事务(session 可继续复用),再 raise,
      把失败如实暴露给调用方,避免假成功.
      业务错误翻译(如 IntegrityError → 40900 幂等回查)由 Service 层负责,
      通用层不做.
    """
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


def has_pending(session: Session) -> bool:
    """判断 Session 是否有未提交变更(new/dirty/deleted 任一非空).

    全空视为无变更:纯读操作不触发无谓提交.
    """
    return bool(session.new or session.dirty or session.deleted)


@contextmanager
def transaction(session: Session):
    """上下文事务:把 with 块内多个写操作包成一个原子单元.

    - 正常退出:提交(失败回滚后原样抛出;无变更时 commit 是 no-op).
    - 异常退出:回滚并原样抛出.
    """
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    else:
        commit_or_rollback(session)


def auto_commit(fn: Callable[..., Any]) -> Callable[..., Any]:
    """函数级兜底提交装饰器.

    适用场景:Celery 任务等无 HTTP 中间件的入口.
    FastAPI 请求统一走 CommitMiddleware,不要在 endpoint 上重复使用本装饰器.

    语义:
    - 函数正常返回后,从 contextvar 读当前 Session;
      有未提交变更则提交(失败回滚+抛出),无变更或无 Session 则跳过.
    - 函数抛异常时不做兜底提交(异常交由上层统一处理,调用方决定是否回滚).

    同时支持同步函数与协程函数.
    """

    if inspect.iscoroutinefunction(fn):

        @wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await fn(*args, **kwargs)
            session = get_current_session()
            if session is not None and has_pending(session):
                commit_or_rollback(session)
            return result

        return async_wrapper

    @wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        result = fn(*args, **kwargs)
        session = get_current_session()
        if session is not None and has_pending(session):
            commit_or_rollback(session)
        return result

    return sync_wrapper
