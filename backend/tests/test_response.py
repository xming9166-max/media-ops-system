import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import ApiCode, ApiException
from app.core.middleware import RequestIDMiddleware
from app.core.response import ApiResponse

test_app = FastAPI()
test_app.add_middleware(RequestIDMiddleware)


@test_app.exception_handler(ApiException)
async def api_exception_handler(request, exc: ApiException) -> ApiResponse:
    return ApiResponse.error(
        http_status=exc.http_status,
        code=exc.code,
        message=exc.message,
        data=exc.data,
    )


@test_app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> ApiResponse:
    return ApiResponse.error(
        http_status=500,
        code=ApiCode.INTERNAL_ERROR,
        message="服务器内部错误",
    )


@test_app.get("/success")
async def success_route() -> ApiResponse:
    return ApiResponse.success(data={"ok": True})


@test_app.get("/boom")
async def boom_route() -> ApiResponse:
    raise ApiException(
        http_status=404,
        code=ApiCode.NOT_FOUND,
        message="资源不存在",
    )


@test_app.get("/oops")
async def oops_route() -> ApiResponse:
    raise RuntimeError("boom")


client = TestClient(test_app)


def _assert_uuid4(value: str) -> None:
    uuid.UUID(value)


def test_success_response_format() -> None:
    response = client.get("/success")
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"] == {"ok": True}
    _assert_uuid4(body["request_id"])


def test_success_response_request_id_in_header() -> None:
    response = client.get("/success")
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_request_id_reused_when_client_provides() -> None:
    response = client.get("/success", headers={"X-Request-ID": "client-trace"})
    assert response.headers["X-Request-ID"] == "client-trace"
    assert response.json()["request_id"] == "client-trace"


def test_request_ids_isolated_between_requests() -> None:
    first = client.get("/success").json()["request_id"]
    second = client.get("/success").json()["request_id"]
    assert first != second


def test_api_exception_returns_contract_error() -> None:
    response = client.get("/boom")
    body = response.json()
    assert response.status_code == 404
    assert body["code"] == ApiCode.NOT_FOUND
    assert body["message"] == "资源不存在"
    assert body["data"] is None
    _assert_uuid4(body["request_id"])


def test_unhandled_exception_returns_internal_error() -> None:
    # raise_server_exceptions=False 模拟真实服务器行为：异常被全局 handler 兜底为 500
    client_no_raise = TestClient(test_app, raise_server_exceptions=False)
    response = client_no_raise.get("/oops")
    body = response.json()
    assert response.status_code == 500
    assert body["code"] == ApiCode.INTERNAL_ERROR
    assert body["message"] == "服务器内部错误"
    assert body["data"] is None


def test_request_id_rejects_malicious_and_falls_back_to_uuid() -> None:
    bad = ['a"b\n<x>y</x>', "x" * 200, "space in id"]
    for h in bad:
        r = client.get("/success", headers={"X-Request-ID": h})
        rid = r.json()["request_id"]
        _assert_uuid4(rid)
        assert r.headers["X-Request-ID"] == rid


def test_request_id_returns_valid_custom_value() -> None:
    for h in ("client-trace", "A1_b.c", "550e8400-e29b-41d4-a716-446655440000"):
        r = client.get("/success", headers={"X-Request-ID": h})
        assert r.json()["request_id"] == h
        assert r.headers["X-Request-ID"] == h
