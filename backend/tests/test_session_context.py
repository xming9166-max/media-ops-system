"""测试 Session 上下文(contextvar / Repository 缺省取用 / transaction / auto_commit)."""

import pytest
from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.db.base import Base, TimestampMixin
from app.core.db.repository import RepositoryBase
from app.core.db.session import _session_var, get_current_session
from app.core.db.transaction import auto_commit, has_pending, transaction


class _CtxItem(Base, TimestampMixin):
    __tablename__ = "_test_ctx_item"
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class _CtxRepo(RepositoryBase[_CtxItem]):
    model = _CtxItem


def _make_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


# ---------- get_current_session / contextvar ----------


def test_get_current_session_default_none() -> None:
    """无上下文时返回 None."""
    assert get_current_session() is None


def test_contextvar_set_and_reset() -> None:
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    token = _session_var.set(session)
    try:
        assert get_current_session() is session
    finally:
        _session_var.reset(token)
    assert get_current_session() is None


def test_repository_fetches_session_from_contextvar() -> None:
    """Repository 无参构造时从 contextvar 自动取 session(方案一)."""
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    token = _session_var.set(session)
    try:
        repo = _CtxRepo()
        assert repo.session is session
        repo.add(_CtxItem(name="a"))
        session.commit()
        assert repo.count() == 1
    finally:
        _session_var.reset(token)


def test_repository_explicit_session_overrides_contextvar() -> None:
    """显式传入优先于 contextvar."""
    engine = _make_engine()
    ctx_session = sessionmaker(bind=engine)()
    explicit = sessionmaker(bind=engine)()
    token = _session_var.set(ctx_session)
    try:
        repo = _CtxRepo(explicit)
        assert repo.session is explicit
        assert repo.session is not ctx_session
    finally:
        _session_var.reset(token)


# ---------- has_pending ----------


def test_has_pending_false_when_clean() -> None:
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    assert has_pending(session) is False


def test_has_pending_true_when_dirty() -> None:
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    session.add(_CtxItem(name="x"))
    assert has_pending(session) is True
    session.rollback()


# ---------- transaction 上下文管理器 ----------


def test_transaction_commits_on_normal_exit() -> None:
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    with transaction(session):
        session.add(_CtxItem(name="tx-ok"))
    assert has_pending(session) is False
    from sqlalchemy import select

    rows = session.execute(select(_CtxItem)).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "tx-ok"


def test_transaction_rolls_back_on_exception() -> None:
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    with pytest.raises(RuntimeError), transaction(session):
        session.add(_CtxItem(name="tx-bad"))
        raise RuntimeError("boom")
    assert has_pending(session) is False


# ---------- auto_commit 装饰器 ----------


def test_auto_commit_commits_pending_changes() -> None:
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    token = _session_var.set(session)

    @auto_commit
    def business():
        session.add(_CtxItem(name="decorated"))

    try:
        business()  # 函数内不显式 commit,装饰器兜底提交
    finally:
        _session_var.reset(token)

    from sqlalchemy import select

    rows = session.execute(select(_CtxItem)).scalars().all()
    assert len(rows) == 1


def test_auto_commit_skips_when_no_pending() -> None:
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    token = _session_var.set(session)

    @auto_commit
    def readonly():
        return "value"

    try:
        assert readonly() == "value"  # 无变更,跳过提交不报错
    finally:
        _session_var.reset(token)


def test_auto_commit_skips_without_session() -> None:
    """无 contextvar session(Celery 等未注入场景)时静默跳过."""

    @auto_commit
    def business():
        return "done"

    assert business() == "done"


def test_auto_commit_does_not_swallow_exception() -> None:
    """函数异常时装饰器不吞异常(无兜底提交)."""
    engine = _make_engine()
    session = sessionmaker(bind=engine)()
    token = _session_var.set(session)

    @auto_commit
    def failing():
        session.add(_CtxItem(name="never"))
        raise RuntimeError("boom")

    try:
        with pytest.raises(RuntimeError):
            failing()
        # 异常路径:装饰器不提交;变更仍在 session 中未落库(由调用方决定回滚)
        assert has_pending(session) is True
    finally:
        _session_var.reset(token)
        session.rollback()
