from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from structlog.contextvars import get_contextvars

from .pii import scrub_text


AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def write_audit_event(
    *,
    action: str,
    target: str,
    before: Any,
    after: Any,
    actor: str = "api",
) -> dict[str, Any]:
    """Append a security-friendly record for an important state change."""
    context = get_contextvars()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "audit_event",
        "action": action,
        "target": target,
        "actor": actor,
        "correlation_id": context.get("correlation_id", "MISSING"),
        "env": os.getenv("APP_ENV", "dev"),
        "before": _scrub(before),
        "after": _scrub(after),
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
