"""测试声明式基类与 Mixin."""

from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.core.db.base import Base, TimestampMixin, VersionMixin


class _Account(Base, TimestampMixin, VersionMixin):
    __tablename__ = "_test_account"
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_timestamp_mixin_sets_created_and_updated() -> None:
    session = _make_session()
    acc = _Account(name="alice")
    session.add(acc)
    session.commit()
    assert acc.created_at is not None
    assert acc.updated_at is not None
    assert acc.id == 1


def test_version_mixin_starts_at_one() -> None:
    session = _make_session()
    acc = _Account(name="alice")
    session.add(acc)
    session.commit()
    assert acc.version == 1


def test_version_increments_on_update() -> None:
    session = _make_session()
    acc = _Account(name="alice")
    session.add(acc)
    session.commit()
    acc.name = "bob"
    session.commit()
    assert acc.version == 2


def test_optimistic_lock_conflict_raises() -> None:
    """并发同版本更新应抛 StaleDataError."""
    from sqlalchemy.orm.exc import StaleDataError

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    a = _Account(name="alice")
    s1 = SessionLocal()
    s1.add(a)
    s1.commit()

    # 两个 session 各自加载同一版本
    s2 = SessionLocal()
    s3 = SessionLocal()
    a2 = s2.get(_Account, a.id)
    a3 = s3.get(_Account, a.id)

    a2.name = "from_s2"
    s2.commit()

    a3.name = "from_s3"  # 基于旧 version 更新
    try:
        s3.commit()
    except StaleDataError:
        pass
    else:
        raise AssertionError("expected StaleDataError")
