"""权限扩展点与常用工具。

框架只提供权限判定接口与依赖工厂，不内置具体角色/权限模型。
业务系统可继承 ``PermissionBackend`` 实现 RBAC/ABAC。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PermissionBackend(ABC):
    """权限后端抽象。

    业务模块实现此类并注册，即可在 ``require_permission`` 中使用自定义权限逻辑。
    """

    @abstractmethod
    async def resolve(self, user_id: str, context: dict[str, Any] | None = None) -> set[str]:
        """解析用户权限集合。"""


# 全局权限后端实例，业务模块可通过 ``set_permission_backend`` 注入。
_Backend: PermissionBackend | None = None


def set_permission_backend(backend: PermissionBackend) -> None:
    """注册业务权限后端。"""
    global _Backend
    _Backend = backend


def get_permission_backend() -> PermissionBackend | None:
    """获取当前权限后端；未注册时返回 None。"""
    return _Backend
