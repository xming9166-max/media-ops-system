"""数据库基础设施层.

提供声明式基类 / 通用 Mixin / 会话工厂 / Repository 基类 / 软删除归档 Mixin.

依赖方向:Repository -> session -> engine -> DB.
事务边界由 Service 控制,Repository 不 commit.
"""
