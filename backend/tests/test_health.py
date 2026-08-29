from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FRONTEND_ORIGIN = "http://localhost:5173"


def test_cors_preflight_allows_frontend_origin() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN


def test_cors_get_returns_allow_origin_header() -> None:
    response = client.get("/api/v1/health", headers={"Origin": FRONTEND_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN


def test_cors_denies_unlisted_origin() -> None:
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://evil.example.com"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_health_check_returns_200() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_check_returns_ok_status() -> None:
    response = client.get("/api/v1/health")
    assert response.json() == {"status": "ok"}
