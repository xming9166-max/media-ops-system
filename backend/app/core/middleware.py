"""请求级中间件。"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.db.transaction import commit_or_rollback, has_pending
from app.core.logging import get_access_logger
from app.core.request_id import get_request_id, reset_request_id, set_request_id

logger = get_access_logger(__name__)


def register_middleware(app: FastAPI) -> None:
    """统一注册中间件。

    注册顺序（后添加者更外层）：
    - RequestID 最外层（设置 request_id 上下文）
    - AccessLog 在其内层（写日志时 request_id 仍存活）
    - Commit 在其内层（业务返回后兜底提交/回滚）
    - CORS 最内层
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CommitMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求建立统一 request_id。

    - 请求进入时：优先复用请求头 `X-Request-ID`，否则由后端生成 UUID4
    - 响应返回时：写入 `X-Request-ID` 响应头，便于前后端对齐追踪
    - 请求结束：reset 上下文，防止泄漏到其他请求
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        token = set_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = get_request_id()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = get_request_id()
            return response
        finally:
            reset_request_id(token)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """HTTP 访问日志中间件。

    输出字段（恒定）：method / path / status / duration_ms / request_id。
    可选字段（DEBUG 模式或配置开启）：query（结构化 + 脱敏）/ remote_addr /
    user_agent / referer / request_body / response_body。

    设计要点：
    - Query 解析为结构化 dict（``a=1&b=2`` → ``{"a": "1", "b": "2"}``），字符串保真、
      重复键取最后值，解析后统一脱敏。
    - Body 采样受 ``LOG_ACCESS_BODY`` 开关控制（生产默认关闭）；文件上传 / 二进制 /
      流式响应不读取；超出 ``LOG_BODY_MAX_BYTES`` 截断并打标。
    - 慢请求（``duration_ms >= LOG_SLOW_REQUEST_MS``）日志升 WARNING 并打 ``slow: true``。
    - 客户端 IP 默认取 ``client.host``；``LOG_TRUST_PROXY_HEADERS=true`` 时取
      ``X-Forwarded-For`` 首值。
    - 注册时须处于 ``RequestIDMiddleware`` 内层，保证写日志时 request_id 上下文仍存活。
    """

    # 不采样的请求 Content-Type 前缀（文件上传 / 二进制媒体）
    _SKIP_BODY_CONTENT_TYPES = (
        "multipart/form-data",
        "application/octet-stream",
        "image/",
        "video/",
        "audio/",
    )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        import time

        start = time.perf_counter()

        request_body = None
        if settings.log_access_body and self._should_log_request_body(request):
            request_body = await self._read_request_body(request)

        try:
            response = await call_next(request)
        except Exception:
            # 失败请求也必须保留访问轨迹；错误堆栈由全局异常处理器统一记录。
            duration_ms = round((time.perf_counter() - start) * 1000, 3)
            self._log(request, Response(status_code=500), duration_ms, request_body, None)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        response_body = None
        if settings.log_access_body:
            response_body = self._read_response_body(response)

        self._log(request, response, duration_ms, request_body, response_body)
        return response

    def _should_log_request_body(self, request: Request) -> bool:
        content_type = request.headers.get("content-type", "").lower()
        return not any(content_type.startswith(prefix) for prefix in self._SKIP_BODY_CONTENT_TYPES)

    async def _read_request_body(self, request: Request) -> dict | None:
        # 读取完整请求体供业务使用，日志仅显示截断前缀，绝不污染业务读取。
        # 完整 body 由 request.body() 缓存回 request._body，业务后续读到完整内容。
        try:
            raw = await request.body()
        except Exception:
            return None
        return self._truncate_body(raw, request.headers.get("content-type", ""))

    def _read_response_body(self, response: Response) -> dict | None:
        # 仅对可读 body 的响应采样，流式响应直接跳过
        raw = getattr(response, "body", None)
        if raw is None:
            return None
        return self._truncate_body(raw, response.headers.get("content-type", ""))

    @staticmethod
    def _decode_body(raw: bytes, content_type: str) -> dict | str:
        if "application/json" in content_type.lower():
            import json

            try:
                return json.loads(raw)
            except Exception:
                pass
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None

    def _truncate_body(self, raw: bytes, content_type: str) -> dict | None:
        """解码并按 ``LOG_BODY_MAX_BYTES`` 截断,超出打标（仅影响日志显示，不影响业务）。

        返回 ``{"content": <解码结果>, "truncated": bool}`` 或 ``None``。
        """
        max_bytes = settings.log_body_max_bytes
        truncated = len(raw) > max_bytes
        limited = raw[:max_bytes] if truncated else raw
        decoded = self._decode_body(limited, content_type)
        if decoded is None:
            return None
        return {"content": decoded, "truncated": truncated}

    def _log(
        self,
        request: Request,
        response: Response,
        duration_ms: float,
        request_body: dict | str | None,
        response_body: dict | str | None,
    ) -> None:
        extra: dict = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }

        if settings.debug:
            extra["query"] = self._parse_query(request.url.query)
            extra["remote_addr"] = self._get_client_ip(request)
            extra["user_agent"] = request.headers.get("user-agent")
            extra["referer"] = request.headers.get("referer")
            if request_body is not None:
                extra["request_body"] = request_body
            if response_body is not None:
                extra["response_body"] = response_body

        is_slow = settings.log_slow_request_ms > 0 and duration_ms >= settings.log_slow_request_ms
        if is_slow:
            extra["slow"] = True

        if is_slow:
            logger.warning("slow request", extra=extra)
        else:
            logger.info("access", extra=extra)

    def _parse_query(self, query_string: str) -> dict[str, str]:
        """解析 Query 为结构化 dict（字符串保真、重复键取最后值）。"""
        from urllib.parse import parse_qsl

        return dict(parse_qsl(query_string, keep_blank_values=True))

    def _get_client_ip(self, request: Request) -> str:
        if settings.log_trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return ""


class CommitMiddleware(BaseHTTPMiddleware):
    """统一入口兜底提交/回滚中间件(只注册一次,全 API 生效).

    语义:
    - 请求正常返回:当前 Session 有未提交变更 → commit_or_rollback 提交;
      无变更(纯读) → 跳过,不做无谓提交.
    - 请求抛异常:回滚当前 Session,再原样抛出交由上层异常处理器.

    Session 从 ``request.state.db_session`` 读取(get_session 依赖写入):
    BaseHTTPMiddleware 的 call_next 在独立 task 中运行,依赖内 set 的
    contextvar 不会传播回中间件,必须经 scope 共享的 request.state.
    无 Session(未配置数据库/未声明依赖)时跳过.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            session = getattr(request.state, "db_session", None)
            if session is not None:
                session.rollback()
            raise
        session = getattr(request.state, "db_session", None)
        if session is not None and has_pending(session):
            commit_or_rollback(session)
        return response


__all__: list[str] = ["RequestIDMiddleware", "AccessLogMiddleware", "CommitMiddleware"]
