"""演示模型:账号(主表) + 账号历史(归档表).

用于验证迁移链路、Repository 基类、软删除归档全流程.
不承载真实业务.
"""

from sqlalchemy import Column, String

from app.core.db.base import Base, TimestampMixin, VersionMixin
from app.core.db.soft_delete import ArchiveHistoryMixin


class Account(Base, TimestampMixin, VersionMixin):
    """账号主表(只存活跃记录)."""

    __tablename__ = "account"

    business_key: str = Column(String(64), unique=True, nullable=False)
    name: str = Column(String(64), nullable=False)


class AccountHistory(Base, ArchiveHistoryMixin):
    """账号历史表(append-only,存储删除时的完整快照)."""

    __tablename__ = "account_history"

    name: str = Column(String(64), nullable=False)
