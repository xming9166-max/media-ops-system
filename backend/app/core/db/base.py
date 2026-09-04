"""声明式基类与通用 Mixin."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类."""


class TimestampMixin:
    """时间戳 Mixin:id / created_at / updated_at.

    - id:自增主键(Integer 保证 SQLite/MySQL 均自动增量;需更大范围可覆写)
    - created_at:插入时由 DB 写入
    - updated_at:插入/更新时由 DB 写入(onupdate=func.now(),方案 A,跨库可测)
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VersionMixin:
    """乐观锁 Mixin.

    通过 SQLAlchemy 的 version_id_col 机制,每次 UPDATE 自动带
    ``WHERE version=?`` 并递增版本;并发冲突时抛 StaleDataError,
    由 Service 捕获转为 ApiException(CONFLICT).

    按需继承,不必所有表都带锁.
    """

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
