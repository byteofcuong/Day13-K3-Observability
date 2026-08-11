from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
EVIDENCE_PATH = Path("submission/evidence/bonus-cost-before-after.json")
PAYLOADS = [
    {"user_id": "bonus-user", "session_id": "bonus-cost", "feature": "qa",
     "message": f"Explain cost optimization example {index}"}
    for index in range(10)
]


def metrics(client: httpx.Client) -> dict:
    response = client.get(f"{BASE_URL}/metrics")
    response.raise_for_status()
    return response.json()


def run_batch(client: httpx.Client) -> dict:
    start = metrics(client)
    for payload in PAYLOADS:
        response = client.post(f"{BASE_URL}/chat", json=payload)
        response.raise_for_status()
    end = metrics(client)
    return {
        "requests": len(PAYLOADS),
        "total_cost_usd": round(end["total_cost_usd"] - start["total_cost_usd"], 6),
        "tokens_out_total": end["tokens_out_total"] - start["tokens_out_total"],
        "metrics_before": start,
        "metrics_after": end,
    }


def main() -> None:
    with httpx.Client(timeout=30.0) as client:
        client.post(f"{BASE_URL}/incidents/cost_spike/enable").raise_for_status()
        client.post(f"{BASE_URL}/config/cost-optimization",
                    params={"enabled": "false", "max_output_tokens": 160}).raise_for_status()
        before = run_batch(client)
        client.post(f"{BASE_URL}/config/cost-optimization",
                    params={"enabled": "true", "max_output_tokens": 160}).raise_for_status()
        after = run_batch(client)
        client.post(f"{BASE_URL}/incidents/cost_spike/disable").raise_for_status()

    saving = round(before["total_cost_usd"] - after["total_cost_usd"], 6)
    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "cost_spike",
        "optimization": {"strategy": "max_output_tokens", "limit": 160},
        "before": before,
        "after": after,
        "cost_saving_usd": saving,
        "cost_saving_pct": round((saving / before["total_cost_usd"]) * 100, 2),
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(f"Saved evidence to {EVIDENCE_PATH}")


if __name__ == "__main__":
    main()
