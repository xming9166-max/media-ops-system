"""Redis 客户端封装(懒初始化单例 + 连接池)."""

from __future__ import annotations

from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings

# 客户端单例(模块级,对应 engine 单例层级)
_client: AsyncRedis | None = None
_pool: ConnectionPool | None = None


def get_redis() -> AsyncRedis | None:
    """按 redis_url 建立 Redis 客户端单例(含连接池).

    未配置 REDIS_URL 时返回 None(无 Redis 可启动).
    """
    global _client, _pool
    if _client is not None:
        return _client
    if not settings.redis_url:
        return None
    _pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    _client = AsyncRedis(connection_pool=_pool)
    return _client


async def close_redis() -> None:
    """释放连接池(供 lifespan 在应用退出时调用)."""
    global _client, _pool
    if _client is not None:
        await _client.close()
        _client = None
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


__all__ = ["get_redis", "close_redis"]
