from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .prompt_management import resolve_prompt
from .tracing import (
    child_generation,
    child_span,
    get_langfuse_client,
    observe,
    score_current_trace,
    tracing_enabled,
)

from structlog.contextvars import get_contextvars


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    # Root observation là span chứ không phải generation: một lượt chat gồm cả
    # bước retrieval lẫn lời gọi LLM, nên retrieval phải là span anh em của
    # generation thay vì nằm lồng bên trong nó.
    @observe(name="chat-response", capture_input=False, capture_output=False)
    def run(self, user_id: str, feature: str, session_id: str, message: str) -> AgentResult:
        started = time.perf_counter()
        langfuse_client = get_langfuse_client()
        question_preview = summarize_text(message)

        with child_span(
            langfuse_client,
            name="retrieve-context",
            input={"question": question_preview},
        ) as retrieval:
            docs = retrieve(message)
            if retrieval is not None:
                retrieval.update(output={"doc_count": len(docs), "docs": docs})

        prompt = resolve_prompt(
            langfuse_client,
            feature=feature,
            docs=docs,
            message=message,
            enabled=tracing_enabled(),
        )

        with child_generation(
            langfuse_client,
            name="llm-answer",
            model=self.model,
            input={"question": question_preview, "doc_count": len(docs)},
        ):
            response = self.llm.generate(prompt.text)
            cost_usd = self._estimate_cost(
                response.usage.input_tokens, response.usage.output_tokens
            )
            langfuse_client.update_current_generation(
                model=self.model,
                output=summarize_text(response.text),
                metadata={
                    "doc_count": len(docs),
                    "query_preview": question_preview,
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_source": prompt.source,
                    "prompt_fetch_error": prompt.fetch_error,
                },
                usage_details={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
                cost_details={"total": cost_usd},
                prompt=prompt.managed_prompt,
            )

        quality_score = self._heuristic_quality(message, response.text, docs)
        latency_ms = int((time.perf_counter() - started) * 1000)

        # correlation_id đến từ middleware qua contextvars. Đây là mắt xích nối
        # trace trên Langfuse với log line trong data/logs.jsonl — thiếu nó thì
        # luồng Metrics → Traces → Logs bị đứt ở đoạn cuối.
        metadata = {
            "prompt_name": prompt.name,
            "prompt_label": prompt.label,
            "prompt_version": prompt.version,
            "prompt_source": prompt.source,
        }
        cid = get_contextvars().get("correlation_id")
        if cid and cid != "MISSING":
            metadata["correlation_id"] = cid

        langfuse_client.update_current_trace(
            name="chat-response",
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, self.model],
            input={"question": question_preview},
            output={"answer": summarize_text(response.text)},
            metadata=metadata,
        )
        score_current_trace(
            langfuse_client,
            name="quality_proxy",
            value=quality_score,
            data_type="NUMERIC",
            comment="Heuristic quality proxy của lab, không phải đánh giá của người dùng",
        )

        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
