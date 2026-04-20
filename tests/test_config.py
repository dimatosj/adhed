def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("API_PORT", "9999")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    import importlib
    from taskstore import config
    importlib.reload(config)
    settings = config.Settings()

    assert settings.database_url == "postgresql+asyncpg://test:test@localhost/test"
    assert settings.api_port == 9999
    assert settings.log_level == "debug"

def test_config_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.delenv("API_PORT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    import importlib
    from taskstore import config
    importlib.reload(config)
    settings = config.Settings()

    assert settings.api_port == 8100
    assert settings.log_level == "info"
