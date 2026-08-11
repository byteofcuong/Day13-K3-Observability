from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import audit
from app.cost_optimization import configure, output_token_limit
from app.incidents import disable, enable
from app.main import app
from app.mock_llm import FakeLLM


def test_output_limit_reduces_cost_spike_tokens(monkeypatch) -> None:
    monkeypatch.setattr("app.mock_llm.random.randint", lambda _low, _high: 180)
    llm = FakeLLM()
    enable("cost_spike")
    try:
        configure(enabled=False, max_output_tokens=160)
        before = llm.generate("short prompt", max_output_tokens=output_token_limit())
        configure(enabled=True, max_output_tokens=160)
        after = llm.generate("short prompt", max_output_tokens=output_token_limit())
    finally:
        disable("cost_spike")
        configure(enabled=False, max_output_tokens=160)

    assert before.usage.output_tokens == 720
    assert after.usage.output_tokens == 160
    assert after.usage.output_tokens < before.usage.output_tokens


def test_incident_and_config_changes_have_separate_audit_log(
    monkeypatch, tmp_path: Path
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", audit_path)

    with TestClient(app) as client:
        enabled = client.post("/incidents/cost_spike/enable", headers={"x-request-id": "audit-01"})
        configured = client.post(
            "/config/cost-optimization?enabled=true&max_output_tokens=140",
            headers={"x-request-id": "audit-02"},
        )
        disabled = client.post("/incidents/cost_spike/disable", headers={"x-request-id": "audit-03"})

    configure(enabled=False, max_output_tokens=160)
    assert enabled.status_code == configured.status_code == disabled.status_code == 200
    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert [record["action"] for record in records] == [
        "incident.enable", "config.change", "incident.disable"
    ]
    assert [record["correlation_id"] for record in records] == [
        "audit-01", "audit-02", "audit-03"
    ]
    assert all(record["before"] != record["after"] for record in records)
