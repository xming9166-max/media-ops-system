"""通用 Repository 基类(单表 CRUD).

职责边界:
- 只封装真·通用操作;业务特有查询由各模块 Repository 继承后自定义.
- 写操作默认不 commit,事务边界由 Service 显式控制;
  当 ``_commit=True`` 时由 Repository 提交当前事务(便捷模式).
- 不含删除语义(删除由 soft_delete 模块提供).
"""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.db.base import Base
from app.core.db.transaction import commit_or_rollback

ModelT = TypeVar("ModelT", bound=Base)


class RepositoryBase(Generic[ModelT]):  # noqa: UP046
    """单表通用 CRUD 基类.

    子类需声明 ``model: type[ModelT]`` 并在构造时传入 Session.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def _commit_if_needed(self, _commit: bool) -> None:
        """按需提交事务.

        _commit=True:Repository 代为提交(便捷模式);失败回滚后原样抛出.
        _commit=False:默认,不提交,由 Service 显式控制事务边界.
        """
        if _commit:
            commit_or_rollback(self.session)

    # ---------- 写入 ----------

    def add(self, obj: ModelT, _commit: bool = False) -> ModelT:
        """插入单条.

        _commit=True 时提交;默认 False,由 Service 显式提交.
        """
        self.session.add(obj)
        self._commit_if_needed(_commit)
        return obj

    def add_all(self, objs: list[ModelT], _commit: bool = False) -> None:
        """批量插入.

        _commit=True 时提交;默认 False,由 Service 显式提交.
        """
        self.session.add_all(objs)
        self._commit_if_needed(_commit)

    def save(self, obj: ModelT, _commit: bool = False) -> ModelT:
        """更新已加载对象(纳入 session + flush).

        _commit=True 时提交;默认 False,由 Service 显式提交.
        """
        self.session.add(obj)
        self.session.flush()
        self._commit_if_needed(_commit)
        return obj

    def save_all(self, objs: Sequence[ModelT], _commit: bool = False) -> None:
        """批量更新已加载对象.

        _commit=True 时提交;默认 False,由 Service 显式提交.
        """
        for obj in objs:
            self.session.add(obj)
        self.session.flush()
        self._commit_if_needed(_commit)

    def bulk_insert(self, rows: list[dict[str, Any]], _commit: bool = False) -> int:
        """大批量导入(Core insert 一次性拼接,跳过 ORM 事件).

        返回受影响行数.适用于导入场景,内存友好.
        _commit=True 时提交;默认 False,由 Service 显式提交.
        注意:created_at 等 server_default 由 DB 端填充,仍会写入.
        """
        if not rows:
            return 0
        self.session.execute(self.model.__table__.insert(), rows)
        self._commit_if_needed(_commit)
        return len(rows)

    def update_by(self, values: dict[str, Any], _commit: bool = False, **filters: Any) -> int:
        """条件批量修改(Core bulk,绕乐观锁).

        仅用于非并发敏感的后台批量(状态流转/数据修复等).
        需显式在 values 中传 updated_at=func.now(),否则时间戳不变.
        _commit=True 时提交;默认 False,由 Service 显式提交.
        返回受影响行数.
        """
        stmt = update(self.model).filter_by(**filters).values(**values)
        result = self.session.execute(stmt)
        self._commit_if_needed(_commit)
        return result.rowcount

    def update_by_ids(self, ids: list[int], values: dict[str, Any], _commit: bool = False) -> int:
        """按主键列表批量修改(绕乐观锁).语义同 update_by.

        _commit=True 时提交;默认 False,由 Service 显式提交.
        """
        if not ids:
            return 0
        stmt = update(self.model).where(self.model.id.in_(ids)).values(**values)
        result = self.session.execute(stmt)
        self._commit_if_needed(_commit)
        return result.rowcount

    # ---------- 读取 ----------

    def get(self, id: int) -> ModelT | None:
        """主键查单条."""
        return self.session.get(self.model, id)

    def get_by(self, **filters: Any) -> ModelT | None:
        """按等值条件查单条(应配唯一字段)."""
        stmt = select(self.model).filter_by(**filters)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: str | None = None,
        **filters: Any,
    ) -> list[ModelT]:
        """条件分页列表."""
        stmt = select(self.model).filter_by(**filters)
        if order_by:
            if order_by.startswith("-"):
                stmt = stmt.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                stmt = stmt.order_by(getattr(self.model, order_by).asc())
        stmt = stmt.offset(offset).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def count(self, **filters: Any) -> int:
        """条件计数."""
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        return self.session.execute(stmt).scalar_one()

    def exists(self, **filters: Any) -> bool:
        """是否存在."""
        return self.count(**filters) > 0

    def paginate(
        self, page: int, page_size: int, **filters: Any
    ) -> tuple[Sequence[ModelT], int, int, int]:
        """分页查询,返回(items, total, page, page_size)."""
        items = self.list(offset=(page - 1) * page_size, limit=page_size, **filters)
        total = self.count(**filters)
        return items, total, page, page_size

    def refresh(self, obj: ModelT) -> None:
        """重新拉取 DB 最新值(丢弃本地脏改)."""
        self.session.refresh(obj)
