"""Redis 基础设施层.

提供:
- client.py:get_redis / close_redis 封装(懒初始化单例 + 连接池)
- base.py:RedisBase 通用方法 + 统一 key 前缀规范

REDIS_URL 缺省空串时,服务可无 Redis 启动,避免破坏无依赖测试/CI.
"""
