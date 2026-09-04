"""测试通用 Repository 基类."""

from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.db.base import Base, TimestampMixin
from app.core.db.repository import RepositoryBase


class _Item(Base, TimestampMixin):
    __tablename__ = "_test_item"
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class _ItemRepo(RepositoryBase[_Item]):
    model = _Item


def _make_repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return _ItemRepo(Session())


def test_add_and_get() -> None:
    repo = _make_repo()
    repo.add(_Item(name="a"))
    repo.session.commit()
    got = repo.get(1)
    assert got is not None
    assert got.name == "a"


def test_get_by_unique_field() -> None:
    repo = _make_repo()
    repo.add(_Item(name="alice"))
    repo.session.commit()
    assert repo.get_by(name="alice").name == "alice"
    assert repo.get_by(name="nobody") is None


def test_list_with_pagination() -> None:
    repo = _make_repo()
    for i in range(5):
        repo.add(_Item(name=f"item-{i}"))
    repo.session.commit()
    items = repo.list(offset=1, limit=2, order_by="id")
    assert [i.name for i in items] == ["item-1", "item-2"]


def test_count_and_exists() -> None:
    repo = _make_repo()
    repo.add(_Item(name="x"))
    repo.session.commit()
    assert repo.count() == 1
    assert repo.exists(name="x") is True
    assert repo.exists(name="y") is False


def test_paginate_returns_total() -> None:
    repo = _make_repo()
    for i in range(3):
        repo.add(_Item(name=f"i{i}"))
    repo.session.commit()
    items, total, page, size = repo.paginate(page=1, page_size=2)
    assert len(items) == 2
    assert total == 3
    assert page == 1
    assert size == 2


def test_save_updates_and_flushes() -> None:
    repo = _make_repo()
    repo.add(_Item(name="old"))
    repo.session.commit()
    obj = repo.get(1)
    obj.name = "new"
    repo.save(obj)
    repo.session.commit()
    assert repo.get(1).name == "new"


def test_bulk_insert_returns_rowcount() -> None:
    repo = _make_repo()
    n = repo.bulk_insert([{"name": f"b{i}"} for i in range(10)])
    repo.session.commit()
    assert n == 10
    assert repo.count() == 10


def test_update_by_bulk() -> None:
    repo = _make_repo()
    for i in range(3):
        repo.add(_Item(name=f"u{i}"))
    repo.session.commit()
    from sqlalchemy import func

    affected = repo.update_by({"name": "same", "updated_at": func.now()})
    repo.session.commit()
    assert affected == 3
    assert all(i.name == "same" for i in repo.list(limit=10))


def test_update_by_ids() -> None:
    repo = _make_repo()
    for i in range(4):
        repo.add(_Item(name=f"id{i}"))
    repo.session.commit()
    from sqlalchemy import func

    affected = repo.update_by_ids([1, 3], {"name": "hit", "updated_at": func.now()})
    repo.session.commit()
    assert affected == 2
    assert repo.get(1).name == "hit"
    assert repo.get(2).name == "id1"
    assert repo.get(3).name == "hit"


def test_refresh_reloads_from_db() -> None:
    repo = _make_repo()
    repo.add(_Item(name="orig"))
    repo.session.commit()
    obj = repo.get(1)
    obj.name = "dirty"
    repo.refresh(obj)
    assert obj.name == "orig"
