from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env", override=False)

from structlog.contextvars import bind_contextvars, clear_contextvars

from app.agent import LabAgent
from app.logging_config import LOG_PATH, configure_logging
from app.pii import hash_user_id
from app.tracing import flush, get_langfuse_client, init_tracing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create one reproducible trace for Langfuse prompt-version evidence."
    )
    parser.add_argument("--label", required=True, choices=["baseline", "candidate", "production"])
    parser.add_argument("--step", required=True)
    args = parser.parse_args()

    os.environ["LANGFUSE_PROMPT_LABEL"] = args.label
    configure_logging()
    status = init_tracing()
    if not status["tracing_enabled"]:
        raise SystemExit("Langfuse tracing is not configured in .env")

    correlation_id = f"req-{uuid.uuid4().hex[:8]}"
    session_id = f"prompt-evidence-{uuid.uuid4().hex[:8]}"
    user_id = "prompt-evidence-user"
    clear_contextvars()
    bind_contextvars(
        correlation_id=correlation_id,
        user_id_hash=hash_user_id(user_id),
        session_id=session_id,
        feature="refund",
        model="claude-sonnet-4-5",
        env=os.getenv("APP_ENV", "dev"),
    )

    result = LabAgent().run(
        user_id=user_id,
        feature="refund",
        session_id=session_id,
        message="What is your refund policy?",
    )
    client = get_langfuse_client()
    flush(client)

    trace_id = None
    if LOG_PATH.exists():
        for line in reversed(LOG_PATH.read_text(encoding="utf-8").splitlines()):
            record = json.loads(line)
            if record.get("correlation_id") == correlation_id and record.get("trace_id"):
                trace_id = record["trace_id"]
                break

    print(
        json.dumps(
            {
                "step": args.step,
                "label": args.label,
                "correlation_id": correlation_id,
                "session_id": session_id,
                "trace_id": trace_id,
                "latency_ms": result.latency_ms,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
