"""测试 Redis 基础设施(客户端 + RedisBase 通用方法 + key 前缀 + 锁).

注:redis 客户端为 async,但为免引入 pytest-asyncio 新依赖,
本模块用 asyncio.run() 将异步调用包为同步测试,与项目现有测试风格一致.
"""

import asyncio

import pytest

from app.core.redis.base import RedisBase
from app.core.redis.client import get_redis

# 复用同一个事件循环,避免 asyncio.run() 每次关闭 loop 导致后续调用报 "Event loop is closed".
_loop = asyncio.new_event_loop()


def _run(coroutine):
    """辅助:同步运行一个协程(复用模块级 loop)."""
    return _loop.run_until_complete(coroutine)


# ---------- 客户端 ----------


def test_get_redis_returns_none_when_disabled() -> None:
    """未配置 REDIS_URL 时 get_redis() 返回 None(无 Redis 可启动)."""
    from unittest.mock import patch

    import app.core.redis.client as client_module

    # 重置单例 + 模拟未配置 REDIS_URL
    original = client_module._client
    client_module._client = None
    client_module._pool = None
    with patch.object(client_module.settings, "redis_url", ""):
        try:
            assert get_redis() is None
        finally:
            client_module._client = original


def test_redis_base_handles_missing_client_gracefully() -> None:
    """无 Redis 时所有方法静默跳过,不抛错(对齐无依赖测试/CI)."""
    from unittest.mock import patch

    import app.core.redis.client as client_module

    # 模拟未配置 REDIS_URL + 重置单例,使 fallback 也返回 None
    client_module._client = None
    client_module._pool = None
    with patch.object(client_module.settings, "redis_url", ""):
        base = RedisBase(client=None)
        assert base.redis is None

        _run(base.set_key("k", "v"))
        assert _run(base.get_key("k")) is None
        assert _run(base.delete("k")) == 0
        assert _run(base.exists("k")) is False
        assert _run(base.incr("c")) == 0
        assert _run(base.hget("h", "f")) is None
        assert _run(base.smembers("s")) == set()
        assert _run(base.rpop("q")) is None
        assert _run(base.acquire_lock("lock")) is None


# ---------- key 前缀 ----------


def test_key_prefix_format() -> None:
    """key 前缀格式: {app}:{namespace}:{key}."""
    base = RedisBase(client=None)
    base.namespace = "cache"
    assert base._key("user:123") == f"{base._app_prefix}:cache:user:123"


def test_default_namespace() -> None:
    base = RedisBase(client=None)
    assert base.namespace == "default"
    assert base._key("x") == f"{base._app_prefix}:default:x"


# ---------- 通用方法(需 Redis,无 Redis 时自动跳过) ----------


def test_string_set_get_delete() -> None:
    base = _real_base()
    _run(base.set_key("greet", "hello", ex=60))
    assert _run(base.get_key("greet")) == "hello"
    assert _run(base.exists("greet")) is True
    assert _run(base.delete("greet")) == 1
    assert _run(base.get_key("greet")) is None


def test_incr_decr() -> None:
    base = _real_base()
    _run(base.delete("counter"))
    assert _run(base.incr("counter")) == 1
    assert _run(base.incr("counter", 4)) == 5
    assert _run(base.decr("counter", 2)) == 3


def test_set_nx_idempotent() -> None:
    """set_nx 幂等:首次成功,重复失败."""
    base = _real_base()
    _run(base.delete("nxkey"))
    assert _run(base.set_nx("nxkey", "v1", ex=60)) is True
    assert _run(base.set_nx("nxkey", "v2", ex=60)) is False
    assert _run(base.get_key("nxkey")) == "v1"


def test_expire_ttl() -> None:
    base = _real_base()
    _run(base.set_key("tmp", "v", ex=60))
    assert _run(base.ttl("tmp")) > 0
    _run(base.expire("tmp", 120))
    assert _run(base.ttl("tmp")) >= 60


def test_hash() -> None:
    base = _real_base()
    _run(base.hset("user:1", "name", "alice"))
    _run(base.hset("user:1", "age", "30"))
    assert _run(base.hget("user:1", "name")) == "alice"
    assert _run(base.hgetall("user:1")) == {"name": "alice", "age": "30"}
    assert _run(base.hdel("user:1", "age")) == 1
    assert _run(base.hget("user:1", "age")) is None


def test_set_ops() -> None:
    base = _real_base()
    _run(base.sadd("tags", "a", "b", "c"))
    assert _run(base.smembers("tags")) == {"a", "b", "c"}
    _run(base.srem("tags", "b"))
    assert _run(base.smembers("tags")) == {"a", "c"}


def test_list_queue() -> None:
    base = _real_base()
    _run(base.delete("queue"))
    _run(base.lpush("queue", "a", "b"))
    assert _run(base.llen("queue")) == 2
    assert _run(base.rpop("queue")) == "a"
    assert _run(base.rpop("queue")) == "b"
    assert _run(base.rpop("queue")) is None


def test_distributed_lock() -> None:
    """acquire/release lock + token 校验防误删."""
    base = _real_base()
    _run(base.delete("lock"))
    token = _run(base.acquire_lock("lock", timeout=10))
    assert token is not None
    # 重复获取失败
    assert _run(base.acquire_lock("lock", timeout=10)) is None
    # 错误 token 无法释放
    assert _run(base.release_lock("lock", "wrong-token")) is False
    # 正确 token 释放成功
    assert _run(base.release_lock("lock", token)) is True
    assert _run(base.exists("lock")) is False


def _real_base() -> RedisBase:
    """有 Redis 时提供真实客户端;无 Redis 时跳过(不强制依赖)."""
    client = get_redis()
    if client is None:
        pytest.skip("REDIS_URL 未配置,跳过 Redis 集成测试")
    base = RedisBase(client=client)
    base.namespace = "test"
    return base
