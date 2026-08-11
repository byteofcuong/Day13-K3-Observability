from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.main import app
from app.pii import hash_user_id


def test_middleware_generates_correlation_id_and_response_headers() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert re.fullmatch(r"req-[0-9a-f]{8}", response.headers["x-request-id"])
    assert float(response.headers["x-response-time-ms"]) >= 0


def test_chat_preserves_request_id_and_enriches_all_api_logs(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    payload = {
        "user_id": "student-01",
        "session_id": "session-01",
        "feature": "qa",
        "message": "Explain correlation IDs",
    }
    with TestClient(app) as client:
        response = client.post("/chat", json=payload, headers={"x-request-id": "edge-42"})

    assert response.status_code == 200
    assert response.json()["correlation_id"] == "edge-42"
    assert response.headers["x-request-id"] == "edge-42"

    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    api_events = [event for event in events if event.get("service") == "api"]
    assert {event["event"] for event in api_events} >= {"request_received", "response_sent"}

    for event in api_events:
        assert event["correlation_id"] == "edge-42"
        assert event["user_id_hash"] == hash_user_id(payload["user_id"])
        assert event["user_id_hash"] != payload["user_id"]
        assert event["session_id"] == payload["session_id"]
        assert event["feature"] == payload["feature"]
        assert event["model"] == "claude-sonnet-4-5"
        assert event["env"] == "dev"

