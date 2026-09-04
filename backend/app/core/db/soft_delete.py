"""移动式历史归档软删 Mixin.

语义:删除 = 同一事务内 INSERT 历史表(完整快照)+ DELETE 主表行(原子归档).
主表只存活跃记录,UNIQUE(business_key)天然成立,可重建同键.
历史表 append-only,禁 UPDATE/DELETE.

恢复策略(路径 A 为主 + 可配置 mode):
- RESTORE_OR_FAIL(默认):原地恢复,若 business_key 已被占用则 40900.
- FORCE_NEW:以历史快照新建一条活跃记录(新 id),永不冲突.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db.base import Base
from app.core.db.transaction import commit_or_rollback


class RestoreMode(StrEnum):
    """恢复策略."""

    RESTORE_OR_FAIL = "restore_or_fail"  # 原地恢复,冲突 40900
    FORCE_NEW = "force_new"  # 以快照新建,永不冲突


class ArchiveHistoryMixin:
    """历史表 Mixin:存储删除时的完整快照 + 审计字段.

    子类需声明业务字段与主表一致,并配置 __tablename__.
    """

    # 历史表自身主键(Integer 保证 SQLite/MySQL 均自动增量)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 主表删除那一刻的 id(普通索引,非强外键;经历删→重建后不再指向现存主行)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # 删除时的业务键(便于按键查历史)
    business_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 审计
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delete_reason: Mapped[str | None] = mapped_column(String(256))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    __table_args__ = (Index("ix_archive_entity_deleted", "entity_id", "deleted_at"),)


class MoveToArchiveRepositoryMixin:
    """移动式归档软删 Mixin.

    子类需声明:
    - model:主表 model
    - history_model:历史表 model(含 ArchiveHistoryMixin)
    """

    model: type[Base]
    history_model: type[Base]

    def __init__(self, session: Session) -> None:
        self.session = session

    def _commit_if_needed(self, _commit: bool) -> None:
        """按需提交事务.

        _commit=True:Repository 代为提交(便捷模式);失败回滚后原样抛出.
        _commit=False:默认,不提交,由 Service 显式控制事务边界.
        """
        if _commit:
            commit_or_rollback(self.session)

    def delete(self, obj: Any, *, reason: str | None = None, _commit: bool = False) -> None:
        """删除 = INSERT 历史 + DELETE 主表(原子归档).

        _commit=True 时提交;默认 False,由 Service 显式提交.
        任一步失败全回滚.
        """
        snapshot = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        # 显式字段 + 业务字段快照(id/created_at/updated_at 由历史表自身生成或无需保留)
        explicit_keys = {"id", "created_at", "updated_at", "business_key"}
        history = self.history_model(
            entity_id=obj.id,
            business_key=snapshot.get("business_key", ""),
            deleted_at=datetime.now(),
            delete_reason=reason,
            **{k: v for k, v in snapshot.items() if k not in explicit_keys},
        )
        self.session.add(history)
        self.session.flush()
        self.session.delete(obj)
        self.session.flush()
        self._commit_if_needed(_commit)

    def restore(
        self,
        history_id: int,
        *,
        mode: RestoreMode = RestoreMode.RESTORE_OR_FAIL,
        _commit: bool = False,
    ) -> Any:
        """恢复历史记录.

        路径 A(默认):原地恢复,冲突 40900.
        路径 B(FORCE_NEW):以快照新建活跃记录.
        _commit=True 时提交;默认 False,由 Service 显式提交.
        """
        history = self.session.get(self.history_model, history_id)
        if history is None:
            raise ValueError(f"history {history_id} not found")
        if history.restored_at is not None:
            raise ValueError(f"history {history_id} already restored")

        snapshot = {
            c.name: getattr(history, c.name)
            for c in history.__table__.columns
            if c.name not in ("id", "entity_id", "deleted_at", "delete_reason", "restored_at")
        }

        if mode is RestoreMode.FORCE_NEW:
            obj = self._create_new(snapshot, history)
            self._commit_if_needed(_commit)
            return obj

        # RESTORE_OR_FAIL:检查业务键是否被占用
        existing = self.session.execute(
            select(self.model).filter_by(business_key=history.business_key)
        ).scalar_one_or_none()
        if existing is not None:
            from app.core.errors import ApiCode, ApiException

            raise ApiException(
                http_status=409,
                code=ApiCode.CONFLICT,
                message=f"business_key '{history.business_key}' already in use",
            )
        obj = self._create_new(snapshot, history, restore_mark=True)
        self._commit_if_needed(_commit)
        return obj

    def _create_new(
        self, snapshot: dict[str, Any], history: Any, *, restore_mark: bool = False
    ) -> Any:
        """以快照新建活跃记录,并标记历史 restored_at.

        若 business_key 已被占用,自动加 ``-restored`` 后缀保证唯一
        (FORCE_NEW 语义:永不冲突).
        """
        if snapshot.get("business_key") and self.exists(business_key=snapshot["business_key"]):
            snapshot["business_key"] = f"{snapshot['business_key']}-restored"
        obj = self.model(**snapshot)
        self.session.add(obj)
        self.session.flush()
        if restore_mark:
            history.restored_at = datetime.now()
        return obj

    def get(self, id: int) -> Any:
        """按主键查主表单条."""
        return self.session.get(self.model, id)

    def exists(self, **filters: Any) -> bool:
        """主表是否存在匹配记录."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        return self.session.execute(stmt).scalar_one() > 0

    def get_history(self, history_id: int) -> Any:
        """按历史表主键查单条."""
        return self.session.get(self.history_model, history_id)

    def list_history(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: str | None = None,
        **filters: Any,
    ) -> list[Any]:
        """历史表分页列表."""
        stmt = select(self.history_model).filter_by(**filters)
        if order_by:
            if order_by.startswith("-"):
                stmt = stmt.order_by(getattr(self.history_model, order_by[1:]).desc())
            else:
                stmt = stmt.order_by(getattr(self.history_model, order_by).asc())
        stmt = stmt.offset(offset).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def count_history(self, **filters: Any) -> int:
        """历史表计数."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.history_model).filter_by(**filters)
        return self.session.execute(stmt).scalar_one()
