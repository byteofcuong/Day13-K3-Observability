from __future__ import annotations

import time

from .incidents import STATE
from .logging_config import get_logger
from .tracing import get_langfuse_client, observe

log = get_logger()

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, traces localize them, logs explain root cause."],
    "policy": ["Do not expose PII in logs. Use sanitized summaries only."],
}


@observe(name="rag.retrieve", as_type="span", capture_input=False, capture_output=False)
def retrieve(message: str) -> list[str]:
    started = time.perf_counter()
    incident_active = STATE["rag_slow"]
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if incident_active:
        time.sleep(2.5)
    lowered = message.lower()
    for key, docs in CORPUS.items():
        if key in lowered:
            result = docs
            break
    else:
        result = ["No domain document matched. Use general fallback answer."]

    client = get_langfuse_client()
    get_trace_id = getattr(client, "get_current_trace_id", None)
    trace_id = get_trace_id() if callable(get_trace_id) else None
    log.info(
        "rag_retrieval_completed",
        service="rag",
        span="rag.retrieve",
        trace_id=trace_id,
        latency_ms=int((time.perf_counter() - started) * 1000),
        payload={"rag_slow": incident_active, "doc_count": len(result)},
    )
    return result
