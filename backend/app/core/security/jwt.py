"""JWT 工具：access token 的生成与解析。

默认使用 HS256，密钥、算法、过期时间从配置读取。
所有时间戳均为 UTC。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings
from app.core.errors import ApiCode, ApiException


class TokenClaims:
    """JWT payload 中携带的标准与业务字段。"""

    SUB = "sub"
    EXP = "exp"
    IAT = "iat"


def create_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    """签发 access token。

    Args:
        subject: 用户唯一标识（如 user_id）。
        extra_claims: 额外需要写入 token 的声明（如角色、权限等）。
    """
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)

    claims: dict[str, Any] = {
        TokenClaims.SUB: str(subject),
        TokenClaims.IAT: int(now.timestamp()),
        TokenClaims.EXP: int(expire.timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并校验 access token。

    失败时抛出 ``ApiException(401, 40100)``。
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": [TokenClaims.SUB, TokenClaims.EXP]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiException(
            http_status=401,
            code=ApiCode.UNAUTHORIZED,
            message="登录已过期，请重新登录",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ApiException(
            http_status=401,
            code=ApiCode.UNAUTHORIZED,
            message="无效的认证信息",
        ) from exc
