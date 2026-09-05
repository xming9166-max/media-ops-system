"""安全/认证基础设施统一入口。"""

from app.core.security.auth_provider import (
    AuthProvider,
    AuthUser,
    DefaultAuthProvider,
    get_auth_provider,
    set_auth_provider,
)
from app.core.security.deps import (
    get_current_user,
    get_optional_user,
    require_permission,
)
from app.core.security.jwt import create_access_token, decode_access_token
from app.core.security.permissions import (
    PermissionBackend,
    get_permission_backend,
    set_permission_backend,
)

__all__ = [
    "AuthProvider",
    "AuthUser",
    "DefaultAuthProvider",
    "PermissionBackend",
    "create_access_token",
    "decode_access_token",
    "get_auth_provider",
    "get_current_user",
    "get_optional_user",
    "get_permission_backend",
    "require_permission",
    "set_auth_provider",
    "set_permission_backend",
]
