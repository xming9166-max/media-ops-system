"""JWT 与认证依赖测试。"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.errors import ApiCode
from app.core.security import (
    AuthUser,
    create_access_token,
    decode_access_token,
    get_current_user,
    require_permission,
    set_auth_provider,
)
from app.core.security.auth_provider import DefaultAuthProvider


class _FakeAuthProvider(DefaultAuthProvider):
    """测试用认证提供者：sub 为 'user-1' 时返回用户，其余返回 None。"""

    async def get_user(self, claims):
        sub = claims.get("sub")
        if sub == "user-1":
            return AuthUser(user_id=sub, permissions={"read"})
        return None


@pytest.fixture(autouse=True)
def _reset_provider(monkeypatch):
    """每个测试前重置为默认提供者，避免状态泄漏。"""
    set_auth_provider(DefaultAuthProvider())


def test_create_and_decode_token():
    token = create_access_token(subject="user-1", extra_claims={"role": "admin"})
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["role"] == "admin"
    assert "exp" in claims
    assert "iat" in claims


def test_decode_expired_token():
    # 直接构造一个已过期的 token（绕过 create_access_token 的过期计算）
    past_claims = {
        "sub": "user-1",
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(past_claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(Exception) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.code == ApiCode.UNAUTHORIZED


def test_decode_invalid_token():
    with pytest.raises(Exception) as exc_info:
        decode_access_token("not-a-token")
    assert exc_info.value.code == ApiCode.UNAUTHORIZED


@pytest.mark.anyio
async def test_get_current_user_unauthorized_when_no_credentials():
    with pytest.raises(Exception) as exc_info:
        await get_current_user(None)
    assert exc_info.value.code == ApiCode.UNAUTHORIZED


@pytest.mark.anyio
async def test_get_current_user_unauthorized_when_default_provider():
    token = create_access_token(subject="user-1")

    # 默认提供者返回 None，因此任何 token 都视为未认证
    class FakeCredentials:
        credentials = token

    with pytest.raises(Exception) as exc_info:
        await get_current_user(FakeCredentials())
    assert exc_info.value.code == ApiCode.UNAUTHORIZED


@pytest.mark.anyio
async def test_get_current_user_success():
    set_auth_provider(_FakeAuthProvider())
    token = create_access_token(subject="user-1")

    class FakeCredentials:
        credentials = token

    user = await get_current_user(FakeCredentials())
    assert user.user_id == "user-1"
    assert "read" in user.permissions


@pytest.mark.anyio
async def test_require_permission_allowed():
    set_auth_provider(_FakeAuthProvider())
    token = create_access_token(subject="user-1")

    class FakeCredentials:
        credentials = token

    dep = require_permission("read")
    user = await dep(FakeCredentials())
    assert user.user_id == "user-1"


@pytest.mark.anyio
async def test_require_permission_denied():
    set_auth_provider(_FakeAuthProvider())
    token = create_access_token(subject="user-1")

    class FakeCredentials:
        credentials = token

    dep = require_permission("write")
    with pytest.raises(Exception) as exc_info:
        await dep(FakeCredentials())
    assert exc_info.value.code == ApiCode.FORBIDDEN
