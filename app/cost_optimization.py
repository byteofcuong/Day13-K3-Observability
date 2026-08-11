from __future__ import annotations

import os


STATE = {
    "enabled": os.getenv("COST_OPTIMIZATION_ENABLED", "false").lower() == "true",
    "max_output_tokens": int(os.getenv("MAX_OUTPUT_TOKENS", "160")),
}


def configure(*, enabled: bool, max_output_tokens: int | None = None) -> dict[str, int | bool]:
    if max_output_tokens is not None:
        if not 1 <= max_output_tokens <= 4096:
            raise ValueError("max_output_tokens must be between 1 and 4096")
        STATE["max_output_tokens"] = max_output_tokens
    STATE["enabled"] = enabled
    return status()


def output_token_limit() -> int | None:
    return int(STATE["max_output_tokens"]) if STATE["enabled"] else None


def status() -> dict[str, int | bool]:
    return dict(STATE)
