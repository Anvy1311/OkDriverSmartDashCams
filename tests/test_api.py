from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.config import Settings, settings
from app.database import SessionLocal
from app.models import Camera
from app.services.background import run_heartbeat_cycle


def login(client, username="admin", password="ChangeMe123!"):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()


def test_protected_api_and_openapi(client):
    assert client.get("/api/v1/cameras").status_code == 401
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    payload = login(client)
    assert payload["user"]["role"] == "admin"
    assert client.get("/api/v1/cameras").status_code == 200


def test_map_configuration_and_policy_safe_frontend(client):
    assert client.get("/api/v1/system/map-config").status_code == 401
    login(client)
    config = client.get("/api/v1/system/map-config").json()
    assert config["tile_url"] == "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert config["referrer_policy"] == "strict-origin-when-cross-origin"
    assert "OpenStreetMap contributors" in config["attribution"]
    assert client.get("/").headers["referrer-policy"] == "strict-origin-when-cross-origin"
    app_source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    html_source = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "https://tile.openstreetmap.org/{z}/{x}/{y}.png" in app_source
    assert "{s}.tile.openstreetmap.org" not in app_source
    assert "referrerPolicy: config.referrerPolicy" in app_source
    assert 'name="referrer"' in html_source
    with pytest.raises(ValidationError):
        Settings(_env_file=None, map_tile_url="http://tiles.example.com/{z}/{x}/{y}.png")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, map_tile_url="https://tiles.example.com/{z}/{x}.png")


def test_service_key_event_ingestion_and_protected_reads(client):
    original_key = settings.analytics_api_key
    settings.analytics_api_key = "test-analytics-service-key"
    try:
        response = client.post(
            "/api/v1/events",
            json={
                "camera_id": "C001",
                "event_type": "ANPR",
                "entity_identifier": "GJ01AB1234",
                "confidence": 0.97,
                "idempotency_key": "service-key-event-1",
            },
            headers={"X-Analytics-Key": "test-analytics-service-key"},
        )
        assert response.status_code == 202
        assert response.json()["event"]["source"] == "api"
        assert client.get("/api/v1/events").status_code == 401
        assert (
            client.post(
                "/api/v1/events",
                json={"camera_id": "C001", "event_type": "ANPR", "entity_identifier": "GJ01AB1234"},
                headers={"X-Analytics-Key": "wrong-key"},
            ).status_code
            == 401
        )
    finally:
        settings.analytics_api_key = original_key


def test_camera_registry_crud_stream_and_gap_report(client):
    login(client)
    payload = {
        "camera_id": "TEST-001",
        "name": "Test camera source",
        "department": "Quality Engineering",
        "latitude": 23.1,
        "longitude": 72.6,
        "camera_type": "FIXED_DOME",
        "source_protocol": "ONVIF",
        "stream_endpoint": "sim://onvif/test-001",
        "zone": "Test Zone",
        "storage_provider": "Test NAS",
        "storage_retention_days": 7,
    }
    invalid_stream = {**payload, "camera_id": "SECRET-001", "stream_endpoint": "rtsp://camera.local/live?apikey=secret"}
    assert client.post("/api/v1/cameras", json=invalid_stream).status_code == 422
    userinfo_stream = {**payload, "camera_id": "SECRET-002", "stream_endpoint": "rtsp://user:pass@camera.local/live"}
    assert client.post("/api/v1/cameras", json=userinfo_stream).status_code == 422
    created = client.post("/api/v1/cameras", json=payload)
    assert created.status_code == 201
    assert created.json()["camera_id"] == "TEST-001"
    assert created.json()["active_alert_count"] == 0
    assert created.json()["highest_alert_severity"] is None
    duplicate = client.post("/api/v1/cameras", json=payload)
    assert duplicate.status_code == 409
    updated = client.patch("/api/v1/cameras/TEST-001", json={"name": "Updated test source"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated test source"
    stream = client.get("/api/v1/cameras/TEST-001/stream")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("image/svg+xml")
    assert "TEST-001" in stream.text
    assert client.get("/api/v1/cameras/export.csv").status_code == 200
    assert client.get("/api/v1/cameras/gap-analysis").json()["total_zones"] >= 6
    history = client.get("/api/v1/cameras/TEST-001/status-history")
    assert history.status_code == 200
    assert len(history.json()) >= 1
    disabled = client.delete("/api/v1/cameras/TEST-001")
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["status"] == "OFFLINE"
    assert client.get("/api/v1/cameras/TEST-001/stream").status_code == 409
    assert client.post("/api/v1/cameras/TEST-001/heartbeat").status_code == 409
    disabled_event = client.post(
        "/api/v1/events",
        json={"camera_id": "TEST-001", "event_type": "ANPR", "entity_identifier": "GJ01AB1234"},
    )
    assert disabled_event.status_code == 404


def test_analytics_correlation_deduplication_and_route(client):
    login(client)
    event_payload = {
        "camera_id": "C001",
        "event_type": "ANPR",
        "entity_type": "VEHICLE",
        "entity_identifier": "gj01 ab1234",
        "confidence": 0.99,
        "vehicle_type": "CAR",
        "idempotency_key": "test-event-idempotency-1",
        "metadata": {"source": "pytest", "simulated": True},
    }
    first = client.post("/api/v1/events", json=event_payload)
    assert first.status_code == 202
    assert first.json()["duplicate"] is False
    assert first.json()["alert"] is not None
    assert first.json()["event"]["entity_identifier"] == "GJ01AB1234"
    assert first.json()["event"]["entity_type"] == "VEHICLE"
    assert client.get("/api/v1/events?q=C001").json()["total"] >= 1
    assert client.get("/api/v1/events?q=ANPR").json()["total"] >= 1
    second = client.post("/api/v1/events", json=event_payload)
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    assert second.json()["event"]["id"] == first.json()["event"]["id"]
    history = client.get("/api/v1/events/entities/GJ01AB1234/history")
    assert history.status_code == 200
    assert history.json()["total"] >= 4
    assert len(history.json()["route"]) == history.json()["total"]
    alert_id = first.json()["alert"]["id"]
    camera_with_alert = client.get("/api/v1/cameras/C001").json()
    assert camera_with_alert["active_alert_count"] >= 1
    assert camera_with_alert["highest_alert_severity"] in {"HIGH", "CRITICAL"}
    assert client.post(f"/api/v1/alerts/{alert_id}/acknowledge").status_code == 200
    acknowledged = client.get(f"/api/v1/alerts/{alert_id}").json()
    assert acknowledged["status"] == "ACKNOWLEDGED"
    assert client.post(f"/api/v1/alerts/{alert_id}/resolve").status_code == 200
    assert client.get(f"/api/v1/alerts/{alert_id}").json()["status"] == "RESOLVED"
    person_event = client.post(
        "/api/v1/events",
        json={
            "camera_id": "C001",
            "event_type": "PERSON_DETECTION",
            "entity_identifier": "PERSON-0042",
            "confidence": 0.91,
            "idempotency_key": "test-person-classification-1",
        },
    )
    assert person_event.status_code == 202
    assert person_event.json()["event"]["entity_type"] == "PERSON"
    assert person_event.json()["alert"] is not None


def test_watchlist_rbac_and_realtime_websocket(client):
    operator = login(client, "operator", "Operator123!")
    assert operator["user"]["role"] == "operator"
    watchlist_payload = {
        "entity_type": "VEHICLE",
        "identifier": "GJ09TEST01",
        "display_name": "Test vehicle",
        "reason": "Synthetic test record",
        "severity": "HIGH",
    }
    assert client.post("/api/v1/watchlist", json=watchlist_payload).status_code == 403
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_text("ping")
        assert websocket.receive_json()["type"] == "pong"
        detection = client.post(
            "/api/v1/events/simulator/emit",
            json={"camera_id": "C001", "entity_identifier": "UNLISTED-001"},
        )
        assert detection.status_code == 202
        broadcast = websocket.receive_json()
        assert broadcast["type"] == "detection"
        assert broadcast["event"]["entity_identifier"] == "UNLISTED-001"
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        health = client.post("/api/v1/cameras/C001/heartbeat?status=DEGRADED")
        assert health.status_code == 200
        broadcast = websocket.receive_json()
        assert broadcast["type"] == "camera.health"
        assert broadcast["camera"]["camera_id"] == "C001"
        assert client.post("/api/v1/cameras/C001/heartbeat?status=ONLINE").status_code == 200
    client.post("/api/v1/auth/logout")
    login(client)
    assert any(entry["action"] == "auth.logout" for entry in client.get("/api/v1/dashboard/activity").json())
    created = client.post("/api/v1/watchlist", json=watchlist_payload)
    assert created.status_code == 201
    assert created.json()["identifier"] == "GJ09TEST01"
    entries = client.get("/api/v1/watchlist?q=GJ09TEST01").json()
    assert len(entries) == 1
    assert client.patch(f"/api/v1/watchlist/{entries[0]['id']}", json={"active": False}).status_code == 200


def test_simulator_and_dashboard_stats(client):
    login(client)
    response = client.post("/api/v1/events/simulator/tick")
    assert response.status_code == 202
    assert response.json()["event"]["camera_id"]
    stats = client.get("/api/v1/dashboard/stats")
    assert stats.status_code == 200
    assert stats.json()["total_cameras"] >= 6
    assert stats.json()["total_events"] >= 1
    activity = client.get("/api/v1/dashboard/activity")
    assert activity.status_code == 200
    assert isinstance(activity.json(), list)
    assert client.get("/api/v1/system/readiness").json()["status"] == "ready"


def test_heartbeat_probe_scope_and_status_preservation(client):
    login(client)
    real_camera = client.post(
        "/api/v1/cameras",
        json={
            "camera_id": "REAL-HEALTH-001",
            "name": "External heartbeat boundary",
            "department": "Integration",
            "latitude": 23.1,
            "longitude": 72.6,
            "camera_type": "FIXED_DOME",
            "source_protocol": "RTSP",
            "stream_endpoint": "rtsp://camera.example/live",
            "zone": "Integration Zone",
        },
    )
    assert real_camera.status_code == 201
    with SessionLocal() as db:
        offline = db.scalar(select(Camera).where(Camera.camera_id == "C006"))
        real = db.scalar(select(Camera).where(Camera.camera_id == "REAL-HEALTH-001"))
        assert offline is not None
        assert real is not None
        changes = run_heartbeat_cycle(db)
        db.refresh(offline)
        db.refresh(real)
        assert offline.status == "OFFLINE"
        assert real.last_heartbeat is None
        assert all(change["camera_id"] != "C006" for change in changes)
    assert client.delete("/api/v1/cameras/REAL-HEALTH-001").status_code == 200


def test_production_settings_reject_unsafe_defaults():
    production_values = {
        "_env_file": None,
        "environment": "production",
        "secret_key": "k" * 64,
        "cookie_secure": True,
        "seed_demo_data": False,
        "simulator_enabled": False,
        "heartbeat_enabled": False,
        "demo_admin_password": "Rotated-admin-secret-123!",
        "demo_operator_password": "Rotated-operator-secret-123!",
    }
    assert Settings(**production_values).environment == "production"
    with pytest.raises(ValidationError):
        Settings(**{**production_values, "secret_key": "replace-this-" + "k" * 64})
    with pytest.raises(ValidationError):
        Settings(**{**production_values, "heartbeat_enabled": True})
    with pytest.raises(ValidationError):
        Settings(**{**production_values, "demo_admin_password": "ChangeMe123!"})
