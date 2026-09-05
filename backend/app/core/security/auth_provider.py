"""认证与权限扩展点。

框架只定义接口，不绑定具体业务实现。后续登录/用户/权限业务由具体模块实现并注册。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AuthUser:
    """当前认证用户的最小抽象。

    业务系统可继承并扩展字段；框架层只依赖 ``user_id`` 与 ``permissions``。
    """

    def __init__(self, user_id: str | int, permissions: set[str] | None = None) -> None:
        self.user_id = str(user_id)
        self.permissions = permissions or set()


class AuthProvider(ABC):
    """认证信息提供者抽象。

    业务模块通过实现此类并注册，把 token 中的 claims 映射为业务用户。
    默认实现返回空用户（未认证占位），保证框架在无业务实现时也能启动。
    """

    @abstractmethod
    async def get_user(self, claims: dict[str, Any]) -> AuthUser | None:
        """根据 JWT claims 获取业务用户；返回 None 表示未认证。"""

    @abstractmethod
    async def get_permissions(self, user: AuthUser) -> set[str]:
        """返回用户拥有的权限标识集合。"""


class DefaultAuthProvider(AuthProvider):
    """默认占位实现：任何 token 都视为未认证。

    仅用于框架启动时不依赖业务用户表；真实项目必须替换。
    """

    async def get_user(self, claims: dict[str, Any]) -> AuthUser | None:
        return None

    async def get_permissions(self, user: AuthUser) -> set[str]:
        return set()


# 全局可替换的 provider 实例。业务模块在启动时通过 ``set_auth_provider`` 注入实现。
_Provider: AuthProvider | None = None


def set_auth_provider(provider: AuthProvider) -> None:
    """注册业务认证提供者。"""
    global _Provider
    _Provider = provider


def get_auth_provider() -> AuthProvider:
    """获取当前认证提供者；未注册时返回默认占位实现。"""
    return _Provider if _Provider is not None else DefaultAuthProvider()
