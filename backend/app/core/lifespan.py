"""应用生命周期管理。

启动阶段无操作(engine/redis 均为懒初始化,保持服务可无依赖启动);
关闭阶段按序释放 Redis 连接池与数据库 engine 连接池。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db.session import dispose_engine
from app.core.redis.client import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用 lifespan:关闭时释放外部连接池。"""
    # 启动阶段保持懒加载,不主动连 DB/Redis(支持无依赖启动)
    yield
    # 关闭阶段
    await close_redis()
    dispose_engine()
