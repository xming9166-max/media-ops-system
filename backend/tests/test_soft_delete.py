"""测试移动式历史归档软删(通用机制 + 恢复原 id + source_id)."""

import pytest
from sqlalchemy import String, UniqueConstraint, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.db.base import Base, TimestampMixin, VersionMixin
from app.core.db.soft_delete import ArchiveHistoryMixin, MoveToArchiveRepositoryMixin
from app.core.errors import ApiCode, ApiException


class _AccountColumns:
    """共享业务列(主表/历史表复用;无唯一约束)."""

    business_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class _Account(Base, TimestampMixin, VersionMixin, _AccountColumns):
    __tablename__ = "_test_archive_account"

    __table_args__ = (UniqueConstraint("business_key"),)


class _AccountHistory(Base, ArchiveHistoryMixin, _AccountColumns):
    __tablename__ = "_test_archive_account_history"


class _AccountRepo(MoveToArchiveRepositoryMixin):
    model = _Account
    history_model = _AccountHistory


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


# ---------- 删除(快照 + 原子归档) ----------


def test_delete_snapshots_business_columns_and_source_id() -> None:
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, reason="test")
    repo.session.commit()

    assert repo.get(acc.id) is None
    history = repo.list_history(limit=10)
    assert len(history) == 1
    assert history[0].source_id == acc.id  # 原主表 id
    assert history[0].business_key == "alice"
    assert history[0].name == "name-alice"
    assert history[0].delete_reason == "test"
    assert history[0].deleted_at is not None


def test_delete_does_not_copy_main_only_columns() -> None:
    """主表专属列(created_at/updated_at/version)不属于业务列,不进历史表."""
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc)
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    assert not hasattr(history, "version")
    assert not hasattr(history, "updated_at")
    assert not hasattr(history, "created_at")


def test_delete_with_commit_persists() -> None:
    """delete(_commit=True) 应提交:主表移除 + 历史落档,无需手动 commit."""
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, reason="auto-commit", _commit=True)

    assert repo.get(acc.id) is None
    history = repo.list_history(limit=10)
    assert len(history) == 1
    assert history[0].delete_reason == "auto-commit"


def test_soft_delete_default_no_commit_rollback_safe() -> None:
    """默认 _commit=False:rollback 后主表与历史均回到删除前状态."""
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, reason="no-commit")

    repo.session.rollback()
    assert repo.get(acc.id) is not None
    assert repo.count_history() == 0


# ---------- 恢复(还原原 id + 全部业务字段) ----------


def test_restore_restores_original_id_and_all_fields() -> None:
    """恢复 = 还原主表原 id(source_id) + 全部业务字段."""
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc)
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    restored = repo.restore(history.id)
    repo.session.commit()

    assert restored.id == acc.id  # 恢复原 id
    assert restored.business_key == "alice"
    assert restored.name == "name-alice"
    assert repo.get(acc.id) is not None
    assert history.restored_at is not None


def test_restore_with_commit_persists() -> None:
    repo = _make_repo()
    acc = _seed(repo)
    repo.delete(acc, _commit=True)

    history = repo.list_history(limit=10)[0]
    restored = repo.restore(history.id, _commit=True)

    assert repo.get(restored.id) is not None
    repo.session.expire_all()
    assert repo.get_history(history.id).restored_at is not None


def test_restore_conflict_when_source_id_taken() -> None:
    """删除期间原 id 被新行占用 → 恢复冲突 409."""
    repo = _make_repo()
    acc = _seed(repo, "carol")  # id=1
    repo.delete(acc)
    repo.session.commit()

    # 显式占用原 id
    repo.session.add(_Account(id=acc.id, business_key="other", name="occupier"))
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    with pytest.raises(ApiException) as exc_info:
        repo.restore(history.id)
    assert exc_info.value.code == ApiCode.CONFLICT
    assert exc_info.value.http_status == 409


def test_restore_conflict_when_unique_taken() -> None:
    """主表唯一列(business_key)被重建占用 → 恢复冲突 409(唯一性靠主表约束兜底)."""
    repo = _make_repo()
    acc = _seed(repo, "bob")  # id=1
    repo.delete(acc)
    repo.session.commit()

    # 重建同 business_key(新 id)
    repo.session.add(_Account(business_key="bob", name="rebuilt"))
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    with pytest.raises(ApiException) as exc_info:
        repo.restore(history.id)
    assert exc_info.value.code == ApiCode.CONFLICT
    assert exc_info.value.http_status == 409


def test_restore_conflict_rolls_back_partial_state() -> None:
    """恢复冲突回滚后,主表保持冲突时状态,历史未标记恢复."""
    repo = _make_repo()
    acc = _seed(repo, "bob")
    repo.delete(acc)
    repo.session.commit()

    repo.session.add(_Account(business_key="bob", name="rebuilt"))
    repo.session.commit()

    history = repo.list_history(limit=10)[0]
    with pytest.raises(ApiException):
        repo.restore(history.id)

    assert repo.get_history(history.id).restored_at is None
    # 冲突行(rebuilt)仍在主表
    from sqlalchemy import select

    rows = repo.session.execute(select(_Account).filter_by(business_key="bob")).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "rebuilt"


def test_restore_already_restored_raises() -> None:
    repo = _make_repo()
    acc = _seed(repo, "dan")
    repo.delete(acc)
    repo.session.commit()
    history = repo.list_history(limit=10)[0]
    repo.restore(history.id)
    repo.session.commit()

    with pytest.raises(ValueError, match="already restored"):
        repo.restore(history.id)


def test_repeat_delete_restore_keeps_multiple_histories() -> None:
    """同一原记录 删→恢复→再删:历史表保留多条(独立自增 id 区分)."""
    repo = _make_repo()
    acc = _seed(repo, "erin")

    repo.delete(acc, reason="first")
    repo.session.commit()
    history_1 = repo.list_history(limit=10)[0]
    restored = repo.restore(history_1.id)
    repo.session.commit()

    repo.delete(restored, reason="second")
    repo.session.commit()

    assert repo.count_history() == 2
    reasons = {h.delete_reason for h in repo.list_history(limit=10)}
    assert reasons == {"first", "second"}
    assert all(h.source_id == acc.id for h in repo.list_history(limit=10))


def test_history_business_columns_have_no_unique_constraint() -> None:
    """历史表业务列无唯一约束:可保存 business_key 相同的多条归档."""
    repo = _make_repo()
    acc = _seed(repo, "erin")
    repo.delete(acc)
    repo.session.commit()
    history_1 = repo.list_history(limit=10)[0]
    repo.restore(history_1.id)
    repo.session.commit()
    repo.delete(repo.get(acc.id))
    repo.session.commit()

    rows = repo.list_history(limit=10)
    keys = [r.business_key for r in rows]
    assert keys.count("erin") == 2  # 同键多条历史共存,无唯一约束


def test_history_table_name_convention_enforced() -> None:
    """历史表表名必须为 <主表名>_history,违约定类即报错."""
    from app.core.db.base import Base as _Base

    class _WrongHistory(_Base, ArchiveHistoryMixin, _AccountColumns):
        __tablename__ = "_wrong_history_name"

    with pytest.raises(ValueError, match="_history"):

        class _BadRepo(MoveToArchiveRepositoryMixin):
            model = _Account
            history_model = _WrongHistory


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


def test_main_unique_constraint_still_enforced() -> None:
    """主表 UNIQUE 仍生效(插入重复 business_key 报 IntegrityError)."""
    repo = _make_repo()
    repo.session.add(_Account(business_key="dup", name="a"))
    repo.session.commit()
    repo.session.add(_Account(business_key="dup", name="b"))
    with pytest.raises(IntegrityError):
        repo.session.commit()
    repo.session.rollback()
