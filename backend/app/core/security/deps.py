"""FastAPI 认证/权限依赖。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPBearer

from app.core.errors import ApiCode, ApiException
from app.core.security.auth_provider import AuthUser, get_auth_provider
from app.core.security.jwt import decode_access_token

# 使用 HTTPBearer 从 Authorization 头提取 Bearer token
_security = HTTPBearer(auto_error=False)


def _extract_token(credentials: Any) -> str:
    """从 HTTPBearer 凭据中提取 token 字符串。"""
    if credentials is None:
        raise ApiException(
            http_status=401,
            code=ApiCode.UNAUTHORIZED,
            message="缺少认证信息",
        )
    return credentials.credentials


async def get_current_user(
    credentials: Annotated[Any, Depends(_security)],
) -> AuthUser:
    """依赖注入：解析 JWT 并返回当前认证用户。

    未携带 token、token 无效、或业务层无法识别用户时，均抛 401。
    """
    token = _extract_token(credentials)
    claims = decode_access_token(token)

    provider = get_auth_provider()
    user = await provider.get_user(claims)
    if user is None:
        raise ApiException(
            http_status=401,
            code=ApiCode.UNAUTHORIZED,
            message="用户不存在或已禁用",
        )

    # 业务提供者可通过 get_permissions 刷新/补充权限；返回空集合时保留 get_user 中初始值
    permissions = await provider.get_permissions(user)
    if permissions:
        user.permissions = permissions
    return user


async def get_optional_user(
    credentials: Annotated[Any, Depends(_security)],
) -> AuthUser | None:
    """依赖注入：同 ``get_current_user``，但允许未认证，返回 None。"""
    try:
        return await get_current_user(credentials)
    except ApiException:
        return None


def require_permission(*permissions: str):
    """依赖工厂：要求当前用户具备指定权限中的任意一个。

    示例：
        @router.get("/admin-only")
        async def admin_only(user: Annotated[AuthUser, Depends(require_permission("admin"))]):
            ...
    """

    async def _checker(credentials: Annotated[Any, Depends(_security)]) -> AuthUser:
        user = await get_current_user(credentials)
        if not permissions:
            return user
        if not any(p in user.permissions for p in permissions):
            raise ApiException(
                http_status=403,
                code=ApiCode.FORBIDDEN,
                message="无权限执行此操作",
            )
        return user

    return _checker
