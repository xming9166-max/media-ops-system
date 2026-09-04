"""业务模型集中导入.

Alembic autogenerate 需要所有模型在此被导入,
以确保 Base.metadata 包含全部表.
"""

from app.models.account import Account, AccountHistory

__all__ = ["Account", "AccountHistory"]
