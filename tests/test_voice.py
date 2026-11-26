from types import SimpleNamespace
from fastapi.testclient import TestClient

import app.main as main
from app.security import UserContext, require_user_context


class FakeResponse:
    status_code = 200

    def json(self):
        return {"signed_url": "wss://api.elevenlabs.io/v1/convai/conversation?agent_id=agent_test&token=temp"}


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return FakeResponse()


def test_voice_capabilities_reflect_server_configuration(monkeypatch):
    monkeypatch.setattr(main.cfg, "elevenlabs_api_key", "test-key")
    monkeypatch.setattr(main.cfg, "elevenlabs_agent_id", "agent_test")
    with TestClient(main.app) as client:
        response = client.get("/api/v1/voice/capabilities")
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["provider"] == "elevenlabs"


def test_voice_session_requires_authenticated_identity():
    with TestClient(main.app) as client:
        response = client.post("/api/v1/voice/session")
    assert response.status_code == 401


def test_voice_session_uses_server_key_and_returns_no_store(monkeypatch):
    monkeypatch.setattr(main.cfg, "elevenlabs_api_key", "test-key")
    monkeypatch.setattr(main.cfg, "elevenlabs_agent_id", "agent_test")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)
    main.app.dependency_overrides[require_user_context] = lambda: UserContext(
        user_id="user-1",
        tenant_id="tenant-1",
        scope="tenant",
        role="user",
        office=None,
        permissions={},
        token_id="token-1",
        identity_assertion="signed-assertion",
    )
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/v1/voice/session")
        assert response.status_code == 200
        assert response.json()["signed_url"].startswith("wss://")
        assert response.headers["cache-control"] == "no-store, private"
    finally:
        main.app.dependency_overrides.pop(require_user_context, None)
