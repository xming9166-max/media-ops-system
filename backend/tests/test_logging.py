"""日志系统测试：配置推断、setup_logging 行为、JSON Schema、脱敏、文件路由。"""

import json
import logging
import logging.handlers
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.core.logging import (
    LOG_TYPE_ACCESS,
    LOG_TYPE_APP,
    JsonFormatter,
    MaxLevelFilter,
    MinLevelFilter,
    TypeFilter,
    get_access_logger,
    get_app_logger,
    get_error_logger,
    sanitize,
)
from app.core.middleware import AccessLogMiddleware, RequestIDMiddleware

# ---- 配置推断测试 ----


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """切换到临时目录并清理相关环境变量，保证用例互不影响。"""
    monkeypatch.chdir(tmp_path)
    for var in (
        "APP_ENV",
        "CONFIG_SOURCE",
        "APP_NAME",
        "DEBUG",
        "LOG_ENABLED",
        "LOG_OUTPUT",
        "LOG_LEVEL",
        "LOG_DIR",
        "LOG_ACCESS_BODY",
        "LOG_BODY_MAX_BYTES",
        "LOG_SLOW_REQUEST_MS",
        "LOG_TRUST_PROXY_HEADERS",
    ):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _write_env_file(directory, name: str, content: str) -> None:
    env_dir = directory / "env"
    env_dir.mkdir(exist_ok=True)
    (env_dir / name).write_text(content, encoding="utf-8")


class TestLogConfigInference:
    """未显式设置日志键时，按运行环境推断默认值。"""

    def test_dev_defaults(self, isolated_env):
        _write_env_file(isolated_env, ".env.dev", "")
        settings = load_settings()
        assert settings.log_enabled is True
        assert settings.log_output.value == "console"
        assert settings.log_access_body is True
        assert settings.log_trust_proxy_headers is False

    def test_pro_defaults(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.pro", "")
        monkeypatch.setenv("APP_ENV", "pro")
        settings = load_settings()
        assert settings.log_output.value == "file"
        assert settings.log_access_body is False
        assert settings.log_trust_proxy_headers is True

    def test_test_defaults(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.test", "")
        monkeypatch.setenv("APP_ENV", "test")
        settings = load_settings()
        assert settings.log_output.value == "file"
        assert settings.log_access_body is False
        assert settings.log_trust_proxy_headers is False

    def test_explicit_overrides_inference(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.dev", "")
        monkeypatch.setenv("LOG_OUTPUT", "both")
        monkeypatch.setenv("LOG_ACCESS_BODY", "false")
        monkeypatch.setenv("LOG_TRUST_PROXY_HEADERS", "true")
        settings = load_settings()
        assert settings.log_output.value == "both"
        assert settings.log_access_body is False
        assert settings.log_trust_proxy_headers is True


# ---- setup_logging 行为 ----


class TestSetupLogging:
    """setup_logging 装配行为（主开关、输出位置、幂等）。"""

    def test_disabled_does_not_output(self, monkeypatch):
        """LOG_ENABLED=false 时无输出，且不调用 logging.disable()。"""
        import app.core.logging as logging_mod

        original_disable = logging.disable
        disable_calls = []
        logging.disable = lambda level: disable_calls.append(level)
        try:
            monkeypatch.setattr(logging_mod.settings, "log_enabled", False)
            monkeypatch.setattr(
                logging_mod.settings,
                "log_output",
                logging_mod.settings.log_output.__class__.CONSOLE,
            )
            logging_mod.setup_logging()
            app_logger = logging.getLogger("app")
            non_null = [h for h in app_logger.handlers if not isinstance(h, logging.NullHandler)]
            assert non_null == []
            # 未调用全局 logging.disable()
            assert disable_calls == []
            # logger 调用不抛
            logger = get_app_logger("app.test.disabled")
            logger.info("should not output")
        finally:
            logging.disable = original_disable

    def test_console_mode_attaches_stream_handler(self, monkeypatch):
        import app.core.logging as logging_mod

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.CONSOLE,
        )
        monkeypatch.setattr(
            logging_mod.settings,
            "log_level",
            logging_mod.settings.log_level.__class__.DEBUG,
        )
        logging_mod.setup_logging()
        app_logger = logging.getLogger("app")
        from logging import StreamHandler

        assert any(isinstance(h, StreamHandler) for h in app_logger.handlers)

    def test_file_mode_creates_three_rotating_handlers(self, monkeypatch, tmp_path):
        import app.core.logging as logging_mod

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.FILE,
        )
        monkeypatch.setattr(logging_mod.settings, "log_dir", str(tmp_path))
        logging_mod.setup_logging()
        app_logger = logging.getLogger("app")
        rotating = [
            h for h in app_logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating) == 3
        assert tmp_path.exists()

    def test_both_mode_attaches_all_handlers(self, monkeypatch, tmp_path):
        import app.core.logging as logging_mod

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.BOTH,
        )
        monkeypatch.setattr(logging_mod.settings, "log_dir", str(tmp_path))
        logging_mod.setup_logging()
        app_logger = logging.getLogger("app")
        from logging import StreamHandler

        assert any(isinstance(h, StreamHandler) for h in app_logger.handlers)
        rotating = [
            h for h in app_logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating) == 3

    def test_setup_is_idempotent(self, monkeypatch):
        """多次调用 setup_logging 不会重复挂 handler。"""
        import app.core.logging as logging_mod

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.CONSOLE,
        )
        logging_mod.setup_logging()
        logging_mod.setup_logging()
        app_logger = logging.getLogger("app")
        from logging import StreamHandler

        stream_handlers = [h for h in app_logger.handlers if isinstance(h, StreamHandler)]
        assert len(stream_handlers) == 1


# ---- JSON Schema & Formatter ----


class TestJsonFormatter:
    """JsonFormatter 输出单行 JSON，公共字段恒定。"""

    def test_common_fields_present(self, monkeypatch):
        formatter = JsonFormatter(app_name="test-app", app_env="dev")
        record = logging.LogRecord(
            name="app.x",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.log_type = "app"
        output = formatter.format(record)
        parsed = json.loads(output)
        # 单行
        assert "\n" not in output
        # 公共字段
        for key in (
            "timestamp",
            "level",
            "logger",
            "log_type",
            "app_name",
            "app_env",
            "trace_id",
            "request_id",
            "task_id",
            "user_id",
            "message",
        ):
            assert key in parsed, f"missing field: {key}"
        assert parsed["level"] == "INFO"
        assert parsed["log_type"] == "app"
        assert parsed["app_name"] == "test-app"
        assert parsed["message"] == "hello"

    def test_extra_fields_flattened(self):
        formatter = JsonFormatter(app_name="test-app", app_env="dev")
        record = logging.LogRecord(
            name="app.x",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.log_type = "app"
        record.action = "create"
        record.success = True
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["action"] == "create"
        assert parsed["success"] is True

    def test_exc_info_adds_traceback(self):
        formatter = JsonFormatter(app_name="test-app", app_env="dev")
        record = logging.LogRecord(
            name="app.x",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="boom",
            args=(),
            exc_info=None,
        )
        record.log_type = "error"
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record.exc_info = sys.exc_info()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "traceback" in parsed
        assert "ValueError" in parsed["traceback"]


# ---- Filter ----


class TestFilters:
    def test_type_filter_matches(self):
        f = TypeFilter(LOG_TYPE_APP)
        record = logging.LogRecord("app.x", logging.INFO, "", 0, "", (), None)
        record.log_type = LOG_TYPE_APP
        assert f.filter(record) is True

    def test_type_filter_rejects_mismatch(self):
        f = TypeFilter(LOG_TYPE_APP)
        record = logging.LogRecord("app.x", logging.INFO, "", 0, "", (), None)
        record.log_type = LOG_TYPE_ACCESS
        assert f.filter(record) is False

    def test_max_level_filter(self):
        f = MaxLevelFilter(logging.ERROR)
        below = logging.LogRecord("app.x", logging.WARNING, "", 0, "", (), None)
        at = logging.LogRecord("app.x", logging.ERROR, "", 0, "", (), None)
        assert f.filter(below) is True
        assert f.filter(at) is False

    def test_min_level_filter(self):
        f = MinLevelFilter(logging.ERROR)
        below = logging.LogRecord("app.x", logging.WARNING, "", 0, "", (), None)
        at = logging.LogRecord("app.x", logging.ERROR, "", 0, "", (), None)
        assert f.filter(below) is False
        assert f.filter(at) is True


# ---- 脱敏 ----


class TestSanitize:
    def test_sensitive_key_masked(self):
        result = sanitize({"password": "123456", "name": "tom"})
        assert result["password"] == "***"
        assert result["name"] == "tom"

    def test_various_sensitive_keys(self):
        data = {"api_key": "abc", "Authorization": "Bearer x", "set-cookie": "ok"}
        result = sanitize(data)
        # 键名保留原样，仅值脱敏
        assert result["api_key"] == "***"
        assert result["Authorization"] == "***"
        assert result["set-cookie"] == "***"

    def test_nested_dict(self):
        result = sanitize({"user": {"password": "x", "age": 18}})
        assert result["user"]["password"] == "***"
        assert result["user"]["age"] == 18

    def test_list_values(self):
        result = sanitize([{"token": "x"}, {"name": "y"}])
        assert result[0]["token"] == "***"
        assert result[1]["name"] == "y"

    def test_phone_masking(self):
        assert sanitize("联系电话 13812345678 请保存") == "联系电话 138****5678 请保存"

    def test_email_masking(self):
        assert sanitize("邮箱 alice@example.com") == "邮箱 a***@example.com"

    def test_id_card_masking(self):
        assert sanitize("身份证 110101199001011234") == "身份证 110101********1234"


# ---- 文件路由 ----


class TestFileRouting:
    """三类日志按 log_type + 级别正确路由到对应文件。"""

    def _read_json_lines(self, path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f.read().splitlines() if line.strip()]

    def test_routing_by_type_and_level(self, monkeypatch, tmp_path):
        import app.core.logging as logging_mod

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.FILE,
        )
        monkeypatch.setattr(logging_mod.settings, "log_dir", str(tmp_path))
        monkeypatch.setattr(
            logging_mod.settings,
            "log_level",
            logging_mod.settings.log_level.__class__.DEBUG,
        )
        logging_mod.setup_logging()

        access_logger = get_access_logger("app.test.route.access")
        app_logger = get_app_logger("app.test.route.app")
        error_logger = get_error_logger("app.test.route.error")

        access_logger.info("a")
        app_logger.info("b")
        app_logger.warning("c")
        error_logger.error("d")

        access_records = self._read_json_lines(f"{tmp_path}/access.log")
        app_records = self._read_json_lines(f"{tmp_path}/app.log")
        error_records = self._read_json_lines(f"{tmp_path}/error.log")

        # access.log 只收 access 类型
        assert len(access_records) == 1
        assert access_records[0]["log_type"] == "access"

        # app.log 收 app 类型 INFO/WARNING
        assert len(app_records) == 2
        assert all(r["log_type"] == "app" for r in app_records)

        # error.log 收 ERROR
        assert len(error_records) == 1
        assert error_records[0]["log_type"] == "error"
        assert error_records[0]["level"] == "ERROR"

    def test_error_level_crosses_types_into_error_log(self, monkeypatch, tmp_path):
        """ERROR+ 跨类型统一入 error.log。"""
        import app.core.logging as logging_mod

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.FILE,
        )
        monkeypatch.setattr(logging_mod.settings, "log_dir", str(tmp_path))
        monkeypatch.setattr(
            logging_mod.settings,
            "log_level",
            logging_mod.settings.log_level.__class__.DEBUG,
        )
        logging_mod.setup_logging()

        access_logger = get_access_logger("app.test.cross.access")
        app_logger = get_app_logger("app.test.cross.app")

        # access 类型的 ERROR 也应进 error.log
        access_logger.error("access boom")
        app_logger.error("app boom")

        error_records = self._read_json_lines(f"{tmp_path}/error.log")
        assert len(error_records) == 2
        log_types = {r["log_type"] for r in error_records}
        assert log_types == {"access", "app"}

        # 且不应出现在 access.log / app.log
        assert self._read_json_lines(f"{tmp_path}/access.log") == []
        assert self._read_json_lines(f"{tmp_path}/app.log") == []

    def test_access_app_exclude_error_level(self, monkeypatch, tmp_path):
        """access.log / app.log 不应包含 ERROR+ 记录。"""
        import app.core.logging as logging_mod

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.FILE,
        )
        monkeypatch.setattr(logging_mod.settings, "log_dir", str(tmp_path))
        monkeypatch.setattr(
            logging_mod.settings,
            "log_level",
            logging_mod.settings.log_level.__class__.DEBUG,
        )
        logging_mod.setup_logging()

        app_logger = get_app_logger("app.test.excl.app")
        app_logger.error("boom")

        assert self._read_json_lines(f"{tmp_path}/app.log") == []


# ---- AccessLogMiddleware 集成测试 ----


def _build_test_app(body_logger_enabled: bool = False) -> FastAPI:
    """构建带 RequestID + AccessLog 中间件的测试 app。"""
    from starlette.requests import Request

    from app.core.response import ApiResponse

    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ok")
    async def ok_route():
        return ApiResponse.success(data={"status": "ok"})

    @app.get("/query")
    async def query_route():
        return ApiResponse.success(data={"status": "ok"})

    @app.post("/echo")
    async def echo_route(request: Request):
        body = await request.body()
        return ApiResponse.success(data={"size": len(body)})

    @app.get("/boom")
    async def boom_route():
        raise RuntimeError("kaboom")

    return app


@pytest.fixture()
def access_app(tmp_path, monkeypatch):
    """配置 FILE 模式日志到临时目录,构建测试 app。"""
    import app.core.logging as logging_mod

    monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
    monkeypatch.setattr(
        logging_mod.settings,
        "log_output",
        logging_mod.settings.log_output.__class__.FILE,
    )
    monkeypatch.setattr(logging_mod.settings, "log_dir", str(tmp_path))
    monkeypatch.setattr(
        logging_mod.settings,
        "log_level",
        logging_mod.settings.log_level.__class__.DEBUG,
    )
    monkeypatch.setattr(logging_mod.settings, "log_access_body", False)
    monkeypatch.setattr(logging_mod.settings, "log_slow_request_ms", 0)
    monkeypatch.setattr(logging_mod.settings, "log_trust_proxy_headers", False)
    logging_mod.setup_logging()
    app = _build_test_app()
    return app, tmp_path


class TestAccessLogFields:
    """访问日志字段完整:method/path/status/duration_ms。"""

    def test_common_fields_present(self, access_app):
        app, tmp_path = access_app
        client = TestClient(app)
        r = client.get("/ok")
        assert r.status_code == 200

        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        record = records[0]
        assert record["log_type"] == "access"
        assert record["method"] == "GET"
        assert record["path"] == "/ok"
        assert record["status"] == 200
        assert isinstance(record["duration_ms"], (int, float))
        assert record["duration_ms"] >= 0

    @staticmethod
    def _read_json_lines(path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f.read().splitlines() if line.strip()]


class TestAccessLogRequestIdConsistency:
    """一次请求内 access 日志与 request_id 一致,跨请求隔离。"""

    def test_request_id_matches_response_header(self, access_app):
        app, tmp_path = access_app
        client = TestClient(app)
        r = client.get("/ok")
        response_request_id = r.json()["request_id"]

        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        assert records[0]["request_id"] == response_request_id
        assert records[0]["trace_id"] == response_request_id  # 缺省回落

    def test_request_ids_isolated_between_requests(self, access_app):
        app, tmp_path = access_app
        client = TestClient(app)
        first = client.get("/ok").json()["request_id"]
        second = client.get("/ok").json()["request_id"]
        assert first != second

    @staticmethod
    def _read_json_lines(path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f.read().splitlines() if line.strip()]


class TestAccessLogDesensitization:
    """访问日志端到端脱敏:query 参数中的敏感字段。"""

    def test_sensitive_query_masked(self, access_app, monkeypatch):
        import app.core.logging as logging_mod

        app, tmp_path = access_app
        # 开启 DEBUG 以输出 query 字段
        monkeypatch.setattr(logging_mod.settings, "debug", True)
        logging_mod.setup_logging()

        client = TestClient(app)
        r = client.get("/query?password=secret123&name=tom")
        assert r.status_code == 200

        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        query = records[0]["query"]
        assert query["password"] == "***"
        assert query["name"] == "tom"

    @staticmethod
    def _read_json_lines(path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f.read().splitlines() if line.strip()]


class TestAccessLogBodySampling:
    """Body 采样:JSON body 进日志、截断打标、multipart 跳过。"""

    def test_json_body_logged(self, access_app, monkeypatch):
        import app.core.logging as logging_mod

        app, tmp_path = access_app
        monkeypatch.setattr(logging_mod.settings, "log_access_body", True)
        monkeypatch.setattr(logging_mod.settings, "debug", True)
        logging_mod.setup_logging()

        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/echo", json={"name": "tom", "age": 18})
        assert r.status_code == 200

        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        body = records[0]["request_body"]
        assert body["truncated"] is False
        assert body["content"] == {"name": "tom", "age": 18}

    def test_body_truncated_and_marked(self, access_app, monkeypatch):
        import app.core.logging as logging_mod

        app, tmp_path = access_app
        monkeypatch.setattr(logging_mod.settings, "log_access_body", True)
        monkeypatch.setattr(logging_mod.settings, "debug", True)
        # 设置很小的上限,触发截断
        monkeypatch.setattr(logging_mod.settings, "log_body_max_bytes", 10)
        logging_mod.setup_logging()

        client = TestClient(app, raise_server_exceptions=False)
        big_payload = {"data": "x" * 100}
        r = client.post("/echo", json=big_payload)
        assert r.status_code == 200

        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        body = records[0]["request_body"]
        assert body["truncated"] is True

    @staticmethod
    def _read_json_lines(path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f.read().splitlines() if line.strip()]


class TestSlowRequestAndProxy:
    """慢请求告警 + 代理头信任。"""

    def test_slow_request_warning_and_marked(self, access_app, monkeypatch):
        """慢请求:超阈值时日志升 WARNING 并打 slow 标记。

        直接调用 ``_log`` 传入已知耗时,避免 mock ``perf_counter`` 被其他代码消费。
        """
        import app.core.logging as logging_mod

        app, tmp_path = access_app
        # 设置 50ms 阈值,debug=False 避免 _parse_query 被调用
        monkeypatch.setattr(logging_mod.settings, "log_slow_request_ms", 50)
        monkeypatch.setattr(logging_mod.settings, "debug", False)
        logging_mod.setup_logging()

        # 构造模拟 request/response,直接调用 _log 传入 200ms 耗时
        from unittest.mock import MagicMock

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/ok"
        request.headers = {}
        request.client = MagicMock(host="127.0.0.1")
        response = MagicMock()
        response.status_code = 200
        response.headers = {}

        middleware = AccessLogMiddleware(app)
        middleware._log(request, response, duration_ms=200.0, request_body=None, response_body=None)

        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        assert records[0]["slow"] is True
        assert records[0]["level"] == "WARNING"
        assert records[0]["duration_ms"] == 200.0

    def test_trust_proxy_headers(self, access_app, monkeypatch):
        import app.core.logging as logging_mod

        app, tmp_path = access_app
        monkeypatch.setattr(logging_mod.settings, "log_trust_proxy_headers", True)
        monkeypatch.setattr(logging_mod.settings, "debug", True)
        logging_mod.setup_logging()

        client = TestClient(app)
        r = client.get("/ok", headers={"X-Forwarded-For": "203.0.113.5, 70.41.3.18"})
        assert r.status_code == 200

        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        assert records[0]["remote_addr"] == "203.0.113.5"

    @staticmethod
    def _read_json_lines(path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f.read().splitlines() if line.strip()]


# ---- 异常请求日志回归测试 ----


class TestExceptionLogging:
    """失败访问日志、request_id 关联及完整异常堆栈。"""

    @staticmethod
    def _read_json_lines(path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as file:
            return [json.loads(line) for line in file.read().splitlines() if line.strip()]

    def test_unhandled_request_logs_500_with_original_request_id(self, access_app):
        app, tmp_path = access_app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/boom", headers={"X-Request-ID": "request-error-001"})

        assert response.status_code == 500
        records = self._read_json_lines(f"{tmp_path}/access.log")
        assert len(records) == 1
        assert records[0]["status"] == 500
        assert records[0]["request_id"] == "request-error-001"
        assert records[0]["trace_id"] == "request-error-001"

    def test_global_handler_preserves_full_traceback_and_request_id(self, tmp_path, monkeypatch):
        import asyncio

        from starlette.requests import Request

        import app.core.logging as logging_mod
        from app.main import unhandled_exception_handler

        monkeypatch.setattr(logging_mod.settings, "log_enabled", True)
        monkeypatch.setattr(
            logging_mod.settings,
            "log_output",
            logging_mod.settings.log_output.__class__.FILE,
        )
        monkeypatch.setattr(logging_mod.settings, "log_dir", str(tmp_path))
        logging_mod.setup_logging()

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/nested-boom",
                "headers": [],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
                "scheme": "http",
                "root_path": "",
            }
        )
        request.state.request_id = "request-error-002"

        def inner_failure():
            raise RuntimeError("deep failure detail")

        def outer_failure():
            inner_failure()

        try:
            outer_failure()
        except RuntimeError as exc:
            response = asyncio.run(unhandled_exception_handler(request, exc))

        assert response.status_code == 500
        assert response.headers["X-Request-ID"] == "request-error-002"
        assert json.loads(response.body)["request_id"] == "request-error-002"

        records = self._read_json_lines(f"{tmp_path}/error.log")
        assert len(records) == 1
        record = records[0]
        assert record["request_id"] == "request-error-002"
        assert record["exc_type"] == "RuntimeError"
        assert "deep failure detail" in record["message"]
        assert "outer_failure" in record["traceback"]
        assert "inner_failure" in record["traceback"]
        assert "RuntimeError: deep failure detail" in record["traceback"]
