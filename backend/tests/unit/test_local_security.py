"""FK-HARDEN / FK-LOCAL: browser-origin guard, callback secret, dashboard WS origin."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import agent.main as main


@pytest.fixture
def client():
    # No `with` block: lifespan (DB, WS server, worker) is not started.
    return TestClient(main.app)


def test_health_without_origin_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "media_provider" in r.json()


def test_foreign_origin_rejected(client):
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_cross_site_without_origin_rejected(client):
    r = client.get("/health", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_canvas_origin_allowed_with_cors_header(client):
    r = client.get("/health", headers={"Origin": "http://127.0.0.1:5180"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://127.0.0.1:5180"


def test_other_localhost_port_rejected(client):
    r = client.get("/health", headers={"Origin": "http://127.0.0.1:9999"})
    assert r.status_code == 403


@pytest.mark.parametrize("path", ["/api/ext/eval-tab", "/api/ext/netlog", "/api/test-direct"])
def test_dangerous_endpoints_removed(client, path):
    assert client.post(path, json={}).status_code in (404, 405)


def test_callback_requires_secret(client):
    r = client.post("/api/ext/callback", json={"id": "x"})
    assert r.status_code == 401


@pytest.mark.parametrize("origin", ["https://evil.example", "http://127.0.0.1:9999"])
def test_dashboard_ws_rejects_unlisted_origin(client, origin):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/dashboard", headers={"origin": origin}):
            pass


def test_dashboard_ws_accepts_canvas_origin(client):
    with client.websocket_connect("/ws/dashboard", headers={"origin": "http://127.0.0.1:5180"}):
        pass
