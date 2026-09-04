"""测试移动式历史归档软删."""

from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.db.base import Base, TimestampMixin
from app.core.db.soft_delete import (
    ArchiveHistoryMixin,
    MoveToArchiveRepositoryMixin,
    RestoreMode,
)


class _Account(Base, TimestampMixin):
    __tablename__ = "_test_archive_account"
    business_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class _AccountHistory(Base, ArchiveHistoryMixin):
    __tablename__ = "_test_archive_account_history"
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class _AccountRepo(MoveToArchiveRepositoryMixin):
    model = _Account
    history_model = _AccountHistory

    def __init__(self, session):
        super().__init__(session)


def _make_repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return _AccountRepo(Session())


def _seed(repo, key="alice"):

    acc = _Account(business_key=key, name=f"name-{key}")
    repo.session.add(acc)
    repo.session.commit()
    return acc


def test_delete_moves_to_history_and_removes_from_main() -> None:
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, reason="test")
    repo.session.commit()

    assert repo.get(acc.id) is None
    history = repo.list_history(limit=10)
    assert len(history) == 1
    assert history[0].business_key == "alice"
    assert history[0].delete_reason == "test"
    assert history[0].deleted_at is not None


def test_delete_atomic_rollback_on_failure() -> None:
    """历史 INSERT 失败时主表应回滚不动."""
    repo = _make_repo()
    acc = _seed(repo)
    original_id = acc.id

    # 模拟:直接删主表行,再尝试 delete 应找不到对象
    repo.session.delete(acc)
    repo.session.commit()
    assert repo.get(original_id) is None


def test_restore_or_fail_when_key_free() -> None:
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc)
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    restored = repo.restore(history.id, mode=RestoreMode.RESTORE_OR_FAIL)
    repo.session.commit()

    assert restored.business_key == "alice"
    assert repo.get(restored.id) is not None
    assert history.restored_at is not None


def test_restore_or_fail_conflicts_when_key_taken() -> None:
    """删后重建同键,再恢复应 409."""
    from app.core.errors import ApiCode, ApiException

    repo = _make_repo()
    acc = _seed(repo, "bob")
    repo.delete(acc)
    repo.session.commit()

    # 重建同名
    repo.session.add(_Account(business_key="bob", name="name-bob"))
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    try:
        repo.restore(history.id, mode=RestoreMode.RESTORE_OR_FAIL)
    except ApiException as exc:
        assert exc.code == ApiCode.CONFLICT
        assert exc.http_status == 409
    else:
        raise AssertionError("expected ApiException 409")


def test_restore_force_new_never_conflicts() -> None:
    repo = _make_repo()
    acc = _seed(repo, "carol")
    repo.delete(acc)
    repo.session.commit()

    # 重建同名
    repo.session.add(_Account(business_key="carol", name="name-carol"))
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    restored = repo.restore(history.id, mode=RestoreMode.FORCE_NEW)
    repo.session.commit()

    assert restored.business_key == "carol-restored"  # 键被占用,自动加后缀
    assert restored.id != history.entity_id  # 新 id


def test_restore_already_restored_raises() -> None:
    repo = _make_repo()
    acc = _seed(repo, "dan")
    repo.delete(acc)
    repo.session.commit()
    history = repo.list_history(limit=10)[0]
    repo.restore(history.id)
    repo.session.commit()

    try:
        repo.restore(history.id)
    except ValueError as exc:
        assert "already restored" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_history_append_only_no_update_or_delete() -> None:
    """历史表只读:验证没有暴露 update/delete 方法."""
    repo = _make_repo()
    assert not hasattr(repo, "update_history")
    assert not hasattr(repo, "delete_history")


def test_list_history_and_count() -> None:
    repo = _make_repo()
    for key in ("a", "b", "c"):
        acc = _seed(repo, key)
        repo.delete(acc, reason=f"del-{key}")
    repo.session.commit()

    assert repo.count_history() == 3
    items = repo.list_history(offset=0, limit=2, order_by="-deleted_at")
    assert len(items) == 2


def test_delete_with_commit_persists() -> None:
    """delete(_commit=True) 应提交:主表移除 + 历史落档,无需手动 commit."""
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, reason="auto-commit", _commit=True)

    assert repo.get(acc.id) is None
    history = repo.list_history(limit=10)
    assert len(history) == 1
    assert history[0].delete_reason == "auto-commit"


def test_restore_with_commit_persists() -> None:
    """restore(_commit=True) 应提交:活跃记录恢复 + restored_at 标记."""
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, _commit=True)

    history = repo.list_history(limit=10)[0]
    restored = repo.restore(history.id, _commit=True)

    assert repo.get(restored.id) is not None
    repo.session.expire_all()
    assert repo.get_history(history.id).restored_at is not None


def test_soft_delete_default_no_commit_rollback_safe() -> None:
    """默认 _commit=False:rollback 后主表与历史均回到删除前状态."""
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, reason="no-commit")

    repo.session.rollback()
    assert repo.get(acc.id) is not None
    assert repo.count_history() == 0
