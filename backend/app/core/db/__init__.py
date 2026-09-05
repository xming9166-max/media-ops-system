"""数据库基础设施层.

提供声明式基类 / 通用 Mixin / 会话工厂 / Repository 基类 / 软删除归档 Mixin.

依赖方向:Repository -> session -> engine -> DB.
事务边界由 Service 控制,Repository 不 commit.
"""

from app.core.db.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)
from app.core.db.repository import RepositoryBase, resolve_order_by
from app.core.db.session import (
    _session_var,
    dispose_engine,
    get_current_session,
    get_engine,
    get_session,
    resolve_session,
)
from app.core.db.soft_delete import (
    ArchiveHistoryMixin,
    MoveToArchiveRepositoryMixin,
)
from app.core.db.transaction import (
    auto_commit,
    commit_or_rollback,
    has_pending,
    transaction,
)

__all__ = [
    "ArchiveHistoryMixin",
    "Base",
    "TimestampMixin",
    "VersionMixin",
    "RepositoryBase",
    "MoveToArchiveRepositoryMixin",
    "resolve_order_by",
    "_session_var",
    "dispose_engine",
    "get_current_session",
    "get_engine",
    "get_session",
    "resolve_session",
    "auto_commit",
    "commit_or_rollback",
    "has_pending",
    "transaction",
]
