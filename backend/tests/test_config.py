import pytest

from app.core.config import AppEnv, load_settings


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """切换到临时目录并清理相关环境变量，保证用例互不影响。"""
    monkeypatch.chdir(tmp_path)
    for var in ("APP_ENV", "CONFIG_SOURCE", "APP_NAME", "DEBUG"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _write_env_file(directory, name: str, content: str) -> None:
    """在临时目录的 env/ 子目录中写入环境文件（对齐真实目录结构）。"""
    env_dir = directory / "env"
    env_dir.mkdir(exist_ok=True)
    (env_dir / name).write_text(content, encoding="utf-8")


class TestDefaultSourceByEnv:
    """未显式设置 CONFIG_SOURCE 时，按环境推断默认读取方式。"""

    def test_dev_defaults_to_file(self, isolated_env):
        _write_env_file(isolated_env, ".env.dev", "APP_NAME=from-dev-file")
        settings = load_settings()
        assert settings.app_env == AppEnv.DEV
        assert settings.app_name == "from-dev-file"

    def test_test_defaults_to_env_var_only(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.test", "APP_NAME=from-test-file")
        monkeypatch.setenv("APP_ENV", "test")
        settings = load_settings()
        assert settings.app_env == AppEnv.TEST
        # 文件被忽略，取字段默认值
        assert settings.app_name == "media-ops-system"

    def test_pro_defaults_to_env_var_only(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.pro", "APP_NAME=from-pro-file")
        monkeypatch.setenv("APP_ENV", "pro")
        settings = load_settings()
        assert settings.app_env == AppEnv.PRO
        assert settings.app_name == "media-ops-system"


class TestExplicitConfigSource:
    """显式设置 CONFIG_SOURCE 时总是优先生效。"""

    def test_test_with_explicit_file_reads_env_test(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.test", "APP_NAME=from-test-file")
        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("CONFIG_SOURCE", "file")
        settings = load_settings()
        assert settings.app_name == "from-test-file"

    def test_dev_with_explicit_env_ignores_file(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.dev", "APP_NAME=from-dev-file")
        monkeypatch.setenv("CONFIG_SOURCE", "env")
        settings = load_settings()
        assert settings.app_name == "media-ops-system"


class TestPriorityAndValidation:
    """取值优先级与非法值校验。"""

    def test_env_var_overrides_file_value(self, isolated_env, monkeypatch):
        _write_env_file(isolated_env, ".env.dev", "APP_NAME=from-file")
        monkeypatch.setenv("APP_NAME", "from-env-var")
        settings = load_settings()
        assert settings.app_name == "from-env-var"

    def test_invalid_app_env_raises(self, isolated_env, monkeypatch):
        monkeypatch.setenv("APP_ENV", "staging")
        with pytest.raises(ValueError, match="APP_ENV"):
            load_settings()

    def test_invalid_config_source_raises(self, isolated_env, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("CONFIG_SOURCE", "database")
        with pytest.raises(ValueError, match="CONFIG_SOURCE"):
            load_settings()

    def test_app_env_case_insensitive(self, isolated_env, monkeypatch):
        monkeypatch.setenv("APP_ENV", "PRO")
        settings = load_settings()
        assert settings.app_env == AppEnv.PRO
