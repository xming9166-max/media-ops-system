"""演示模型:账号(主表) + 账号历史(归档表).

用于验证迁移链路、Repository 基类、软删除归档全流程.不承载真实业务.

- 业务列通过共享 mixin(AccountColumns)定义一次,主表/历史表复用;
- 唯一约束只加在主表(历史表业务列无唯一约束,避免多条归档互相冲突);
- 历史表表名遵循约定:<主表名>_history.
"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionMixin
from app.core.db.soft_delete import ArchiveHistoryMixin


class AccountColumns:
    """主表与历史表共享的业务列(定义一次,两表复用;不加唯一约束/索引)."""

    business_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class Account(Base, TimestampMixin, VersionMixin, AccountColumns):
    """账号主表(只存活跃记录;唯一约束在此层)."""

    __tablename__ = "account"

    __table_args__ = (UniqueConstraint("business_key", name="uq_account_business_key"),)


class AccountHistory(Base, ArchiveHistoryMixin, AccountColumns):
    """账号历史表(account_history;业务列无唯一约束,append-only)."""

    __tablename__ = "account_history"
