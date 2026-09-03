"""request ID module via contextvars."""

import re
import uuid
from contextvars import ContextVar

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_REQUEST_ID_MAX = 128
_ALLOWED = re.compile(r"^[A-Za-z0-9_.-]+$")


def sanitize_request_id(value):
    pass
    if not value:
        return None
    value = value.strip()
    if len(value) > _REQUEST_ID_MAX or not _ALLOWED.match(value):
        return None
    return value


def get_request_id():
    rid = _request_id_var.get()
    if not rid:
        rid = str(uuid.uuid4())
        _request_id_var.set(rid)
    return rid


def set_request_id(request_id=None):
    rid = sanitize_request_id(request_id) or str(uuid.uuid4())
    return _request_id_var.set(rid)


def reset_request_id(token):
    _request_id_var.reset(token)


__all__ = ["sanitize_request_id", "get_request_id", "set_request_id", "reset_request_id"]
