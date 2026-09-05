"""移动式历史归档软删(通用机制,不绑定任何业务字段名).

语义:
- 删除 = 同一事务内 INSERT 历史表(主表业务字段完整快照,原 id→source_id)
  + DELETE 主表行(原子归档).
- 恢复 = 以 source_id 还原主表原 id + 全部业务字段;冲突(原 id 或主表唯一列
  已被占用)→ 数据库异常 → 回滚并 409.

约定:
- 历史表表名 = <主表名>_history(Repository 子类定义时强校验).
- 业务列由「共享业务列 mixin」定义一次,主表/历史表复用;
  历史表业务列不加唯一约束(避免多条归档互相冲突),唯一性只由主表约束兜底.
- 历史表 append-only:只 INSERT 与 restored_at 标记,禁 UPDATE/DELETE 业务数据.
- 历史表有独立自增 id 主键;同一原记录可多次删/恢复,保留多条历史.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db.base import Base
from app.core.db.session import get_current_session
from app.core.db.transaction import commit_or_rollback
from app.core.errors import ApiCode, ApiException


class ArchiveHistoryMixin:
    """历史表 Mixin:独立自增 id + source_id(原主表 id) + 审计字段.

    业务列由业务侧「共享业务列 mixin」提供,与主表同名列同类型;
    历史表业务列不加唯一约束(唯一性只由主表约束兜底).
    """

    # 历史表自身主键(独立自增;同一原记录多次删/恢复保留多条历史)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 原主表 id(追溯来源;恢复时以此作为主表 id 还原)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # 审计
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delete_reason: Mapped[str | None] = mapped_column(String(256))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class MoveToArchiveRepositoryMixin:
    """移动式归档软删 Mixin(通用,不绑定业务字段名).

    子类需声明:
    - model:主表 model
    - history_model:历史表 model(含 ArchiveHistoryMixin + 共享业务列,
      表名必须为 <主表名>_history,定义时强校验)
    """

    model: type[Base]
    history_model: type[Base]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # 表名约定强校验:<主表名>_history(快速失败,防止误接错表)
        model = cls.__dict__.get("model")
        history_model = cls.__dict__.get("history_model")
        if model is not None and history_model is not None:
            expected = f"{model.__tablename__}_history"
            actual = history_model.__tablename__
            if actual != expected:
                raise ValueError(f"历史表表名须为 '{expected}'(主表名_history),实际为 '{actual}'")

    def __init__(self, session: Session | None = None) -> None:
        # 显式传入优先;缺省从 contextvar 自动取(方案一,同 RepositoryBase).
        self.session = session or get_current_session()

    def _commit_if_needed(self, _commit: bool) -> None:
        """按需提交事务.

        _commit=True:Repository 代为提交(便捷模式);失败回滚后原样抛出.
        _commit=False:默认,不提交,由 Service 显式控制事务边界.
        """
        if _commit:
            commit_or_rollback(self.session)

    def _business_columns(self) -> list[str]:
        """主表与历史表共有的业务列(即需快照/还原的字段).

        - 排除主表主键(id 由 source_id 承担,不重复复制).
        - 主表专属列(如 created_at/updated_at/version)不在历史表中,自动排除.
        - 历史表专属列(source_id/审计)不在主表中,自动排除.
        机制因此不预设任何业务字段名.
        """
        pk_names = {c.name for c in self.model.__table__.primary_key.columns}
        history_names = {c.name for c in self.history_model.__table__.columns}
        return [
            c.name
            for c in self.model.__table__.columns
            if c.name not in pk_names and c.name in history_names
        ]

    def delete(self, obj: Any, *, reason: str | None = None, _commit: bool = False) -> None:
        """删除 = INSERT 历史(业务字段快照,原 id→source_id) + DELETE 主表(原子归档).

        _commit=True 时提交;默认 False,由 Service 显式提交.
        任一步失败全回滚.
        """
        snapshot = {c: getattr(obj, c) for c in self._business_columns()}
        history = self.history_model(
            source_id=obj.id,
            deleted_at=datetime.now(),
            delete_reason=reason,
            **snapshot,
        )
        self.session.add(history)
        self.session.flush()
        self.session.delete(obj)
        self.session.flush()
        self._commit_if_needed(_commit)

    def restore(self, history_id: int, *, _commit: bool = False) -> Any:
        """恢复:以 source_id 还原主表原 id + 全部业务字段.

        - 原记录只能恢复一次(restored_at 标记).
        - 冲突(原 id 已被占用 / 主表唯一列被占用)→ 回滚并 409
          (唯一性由主表约束兜底,机制不预设业务键).
        """
        history = self.session.get(self.history_model, history_id)
        if history is None:
            raise ValueError(f"history {history_id} not found")
        if history.restored_at is not None:
            raise ValueError(f"history {history_id} already restored")

        snapshot = {c: getattr(history, c) for c in self._business_columns()}
        obj = self.model(id=history.source_id, **snapshot)
        self.session.add(obj)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise ApiException(
                http_status=409,
                code=ApiCode.CONFLICT,
                message=(
                    f"restore conflict: source id {history.source_id} "
                    "or unique columns already in use"
                ),
            ) from None
        history.restored_at = datetime.now()
        self._commit_if_needed(_commit)
        return obj

    def get(self, id: int) -> Any:
        """按主键查主表单条."""
        return self.session.get(self.model, id)

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
