def test_import_server_without_env(monkeypatch):
    monkeypatch.delenv("MP_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MDG_API_KEY", raising=False)

    import importlib

    import sky_mcp.server

    importlib.reload(sky_mcp.server)
