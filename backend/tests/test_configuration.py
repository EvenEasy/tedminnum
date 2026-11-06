import pytest
from pydantic import ValidationError

from ted.infrastructure.config import Settings

DB = "postgresql+asyncpg://test:example@db.invalid/disposable_test"


def config(**kw):
    return Settings(
        _env_file=None,
        database_url=DB,
        app_env="production",
        secure_cookies=True,
        dev_origins=(),
        app_origin="https://work.example",
        **kw,
    )


def test_production_defaults_are_restrictive():
    s = config()
    assert s.allowed_origins == {"https://work.example"}
    assert not s.accepts_origin("http://localhost:5173")
    assert not s.accepts_origin("null")
    assert not s.accepts_origin("https://work.example.evil")


def test_development_origins_are_explicit():
    s = Settings(
        _env_file=None,
        database_url=DB,
        app_env="development",
        secure_cookies=False,
        app_origin="http://localhost:8000",
        dev_origins="http://localhost:5173,http://127.0.0.1:5173",
    )
    assert s.accepts_origin("http://localhost:5173")
    assert s.accepts_origin("http://127.0.0.1:5173")
    assert not s.accepts_origin("http://localhost:5174")


@pytest.mark.parametrize(
    "overrides",
    [
        {"dev_origins": "http://localhost:5173"},
        {"secure_cookies": False},
        {"app_origin": "https://work.example/"},
        {"app_origin": "https://*.example"},
        {"app_origin": "https://user:secret@work.example"},
        {"app_origin": "http://work.example"},
        {"session_hours": 0},
    ],
)
def test_unsafe_configuration_fails_early(overrides):
    values = dict(
        database_url=DB,
        app_env="production",
        secure_cookies=True,
        dev_origins=(),
        app_origin="https://work.example",
        session_hours=12,
    )
    values.update(overrides)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_native_launcher_uses_existing_database_and_process_local_dev_flags(monkeypatch):
    import os

    from ted import dev

    captured = []
    monkeypatch.setenv("DATABASE_URL", DB)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_ORIGIN", "https://work.example")
    monkeypatch.setenv("SECURE_COOKIES", "true")
    monkeypatch.setattr("sys.argv", ["ted-dev", "--frontend-origin", "http://localhost:5173"])
    monkeypatch.setattr(dev.uvicorn, "run", lambda *args, **kwargs: captured.append((args, kwargs)))
    # Register the launcher-mutated variables with monkeypatch so the test restores them.
    monkeypatch.setenv("DEV_ORIGINS", "")
    dev.main()
    assert os.environ["DATABASE_URL"] == DB
    assert os.environ["APP_ENV"] == "development" and os.environ["SECURE_COOKIES"] == "false"
    assert os.environ["DEV_ORIGINS"] == "http://localhost:5173"
    assert captured[0][1]["host"] == "127.0.0.1" and not captured[0][1]["proxy_headers"]
