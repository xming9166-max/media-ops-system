"""测试事务辅助 commit_or_rollback(失败回滚后原样抛出)."""

import pytest
from sqlalchemy import String, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.db.base import Base, TimestampMixin
from app.core.db.repository import RepositoryBase
from app.core.db.transaction import commit_or_rollback


class _UniqueItem(Base, TimestampMixin):
    __tablename__ = "_test_tx_item"
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class _UniqueItemRepo(RepositoryBase[_UniqueItem]):
    model = _UniqueItem


def _make_repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return _UniqueItemRepo(Session())


def test_commit_success() -> None:
    """正常提交成功."""
    repo = _make_repo()
    repo.session.add(_UniqueItem(name="ok"))
    commit_or_rollback(repo.session)
    assert repo.count() == 1


def test_commit_failure_rolls_back_and_raises() -> None:
    """唯一键冲突 → IntegrityError 原样抛出,事务被回滚."""
    repo = _make_repo()
    repo.add(_UniqueItem(name="dup"))
    commit_or_rollback(repo.session)  # 首条落库

    # 第二条同名 → commit 时唯一键冲突
    repo.session.add(_UniqueItem(name="dup"))
    with pytest.raises(IntegrityError):
        commit_or_rollback(repo.session)

    # 回滚后:脏数据(未提交的第二条)不落库
    repo.session.expire_all()
    assert repo.count() == 1


def test_session_reusable_after_commit_failure() -> None:
    """commit 失败回滚后,session 应复位可继续复用."""
    repo = _make_repo()
    repo.add(_UniqueItem(name="first"))
    commit_or_rollback(repo.session)

    repo.session.add(_UniqueItem(name="first"))  # 冲突
    with pytest.raises(IntegrityError):
        commit_or_rollback(repo.session)

    # session 已复位,可继续正常读写并提交
    repo.add(_UniqueItem(name="second"))
    commit_or_rollback(repo.session)
    repo.session.expire_all()
    assert repo.get_by(name="second") is not None
    assert repo.get_by(name="first") is not None


def test_repository_commit_conflict_bubbles_and_not_persisted() -> None:
    """Repository 写操作 _commit=True 遇冲突:异常冒泡 + 数据未落库."""
    repo = _make_repo()
    repo.add(_UniqueItem(name="taken"), _commit=True)

    with pytest.raises(IntegrityError):
        repo.add(_UniqueItem(name="taken"), _commit=True)  # 冲突,异常冒泡
    repo.session.expire_all()

    assert repo.count() == 1  # 第二条未落库
    assert repo.get_by(name="taken") is not None
