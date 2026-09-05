"""Redis 基础类:统一 key 前缀规范 + 通用方法 + 分布式锁原语."""

from __future__ import annotations

import uuid

from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.core.redis.client import get_redis


class RedisBase:
    """Redis 基础类.

    统一 key 前缀规范: ``{app}:{namespace}:{key}``
    - app: 应用前缀(从 settings.app_name),防多应用共用 Redis 冲突;
    - namespace: 业务域(cache/idempotency/lock/queue...),子类声明;
    - key: 业务自身的键(传裸 key,自动拼接前缀).

    通用方法覆盖 string / hash / set / list / 过期TTL;
    + acquire_lock / release_lock 分布式锁原语(对齐 AGENTS 并发/幂等).
    """

    namespace: str = "default"

    def __init__(self, client: AsyncRedis | None = None) -> None:
        # 显式传入优先;缺省从单例自动取(无 Redis 时为 None).
        self.redis = client or get_redis()

    # ---------- key 前缀 ----------

    @property
    def _app_prefix(self) -> str:
        return settings.app_name

    def _key(self, key: str) -> str:
        """拼接统一前缀: {app}:{namespace}:{key}."""
        return f"{self._app_prefix}:{self.namespace}:{key}"

    # ---------- 通用 string ----------

    async def set_key(
        self, key: str, value: str | int | float | bytes, ex: int | None = None
    ) -> None:
        """设置键值(可选过期秒数)."""
        if self.redis is None:
            return
        await self.redis.set(self._key(key), value, ex=ex)

    async def get_key(self, key: str) -> str | None:
        """取值(键不存在/无 Redis 返回 None)."""
        if self.redis is None:
            return None
        return await self.redis.get(self._key(key))

    async def delete(self, *keys: str) -> int:
        """删除一个或多个键,返回实际删除数."""
        if self.redis is None or not keys:
            return 0
        return await self.redis.delete(*[self._key(k) for k in keys])

    async def exists(self, key: str) -> bool:
        """键是否存在."""
        if self.redis is None:
            return False
        return bool(await self.redis.exists(self._key(key)))

    async def incr(self, key: str, amount: int = 1) -> int:
        """计数器递增,返回递增后的值."""
        if self.redis is None:
            return 0
        return await self.redis.incrby(self._key(key), amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """计数器递减."""
        return await self.incr(key, -amount)

    # ---------- set NX(幂等/锁原语) ----------

    async def set_nx(self, key: str, value: str | int | float, ex: int | None = None) -> bool:
        """仅当键不存在时设置(SET NX),返回是否设置成功.

        幂等原语:首次写入成功返回 True,重复写入返回 False.
        """
        if self.redis is None:
            return False
        return bool(await self.redis.set(self._key(key), value, nx=True, ex=ex))

    # ---------- 过期 TTL ----------

    async def expire(self, key: str, seconds: int) -> bool:
        """设置/更新过期秒数."""
        if self.redis is None:
            return False
        return bool(await self.redis.expire(self._key(key), seconds))

    async def ttl(self, key: str) -> int:
        """查询剩余秒数(-1 永不过期, -2 不存在)."""
        if self.redis is None:
            return -2
        return await self.redis.ttl(self._key(key))

    # ---------- hash ----------

    async def hset(self, hash_key: str, field: str, value: str | int | float) -> int:
        """哈希设单字段."""
        if self.redis is None:
            return 0
        return await self.redis.hset(self._key(hash_key), field, value)

    async def hget(self, hash_key: str, field: str) -> str | None:
        """哈希取单字段."""
        if self.redis is None:
            return None
        return await self.redis.hget(self._key(hash_key), field)

    async def hgetall(self, hash_key: str) -> dict[str, str]:
        """哈希取全部字段."""
        if self.redis is None:
            return {}
        return await self.redis.hgetall(self._key(hash_key))

    async def hdel(self, hash_key: str, *fields: str) -> int:
        """哈希删字段."""
        if self.redis is None or not fields:
            return 0
        return await self.redis.hdel(self._key(hash_key), *fields)

    # ---------- set ----------

    async def sadd(self, key: str, *members: str) -> int:
        """集合加元素,返回新增数."""
        if self.redis is None:
            return 0
        return await self.redis.sadd(self._key(key), *members)

    async def smembers(self, key: str) -> set[str]:
        """集合取全部元素."""
        if self.redis is None:
            return set()
        return await self.redis.smembers(self._key(key))

    async def srem(self, key: str, *members: str) -> int:
        """集合删元素."""
        if self.redis is None:
            return 0
        return await self.redis.srem(self._key(key), *members)

    # ---------- list(队列) ----------

    async def lpush(self, key: str, *values: str) -> int:
        """列表左插,返回长度."""
        if self.redis is None:
            return 0
        return await self.redis.lpush(self._key(key), *values)

    async def rpop(self, key: str) -> str | None:
        """列表右弹(出队)."""
        if self.redis is None:
            return None
        return await self.redis.rpop(self._key(key))

    async def llen(self, key: str) -> int:
        """列表长度."""
        if self.redis is None:
            return 0
        return await self.redis.llen(self._key(key))

    # ---------- 分布式锁 ----------

    async def acquire_lock(self, key: str, timeout: int = 10) -> str | None:
        """获取分布式锁(SET NX + 随机 token + 过期).

        返回 token(成功后用于释放锁),失败返回 None.
        """
        token = uuid.uuid4().hex
        if await self.set_nx(key, token, ex=timeout):
            return token
        return None

    async def release_lock(self, key: str, token: str) -> bool:
        """释放分布式锁(校验 token 防误删,原子释放).

        仅当持有者的 token 匹配时才删除.
        """
        if self.redis is None:
            return False
        # 用 Lua 脚本保证"校验 + 删除"原子性.
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(script, 1, self._key(key), token)
        return bool(result)
