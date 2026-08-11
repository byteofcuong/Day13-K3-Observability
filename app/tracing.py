from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

from .pii import scrub_text

try:
    from langfuse import Langfuse, get_client, observe

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - chỉ dùng khi chưa cài requirements
    LANGFUSE_SDK_AVAILABLE = False
    Langfuse = None

    def observe(*args: Any, **kwargs: Any):
        def decorator(func):
            return func

        return decorator

    class _DummyClient:
        def update_current_trace(self, **kwargs: Any) -> None:
            return None

        def update_current_generation(self, **kwargs: Any) -> None:
            return None

        def flush(self) -> None:
            return None

    def get_client():
        return _DummyClient()


def mask_pii(*, data: Any, **_: Any) -> Any:
    """Mask hook của Langfuse: lớp chặn cuối trước khi payload rời process.

    App đã tự redact bằng summarize_text trước khi gắn vào span, nhưng hook này
    bắt cả những field mà SDK tự thu thập, nên PII không lọt lên Langfuse kể cả
    khi một chỗ nào đó quên redact.
    """
    if isinstance(data, str):
        return scrub_text(data)
    if isinstance(data, dict):
        return {key: mask_pii(data=value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [mask_pii(data=item) for item in data]
    return data


_client: Any = None


def get_langfuse_client():
    """Trả client dùng chung, cấu hình sẵn mask PII và environment.

    Phải khởi tạo qua Langfuse(...) chứ không phải get_client(), vì mask và
    environment chỉ nhận được ở constructor.

    QUAN TRỌNG — thứ tự khởi tạo: SDK cache resource manager theo public_key và
    **lần khởi tạo đầu tiên thắng**. Nếu get_client() chạy trước (chính là điều
    @observe làm ở request đầu), resource manager được tạo không có mask và mọi
    lời gọi Langfuse(mask=...) sau đó bị bỏ qua im lặng — PII sẽ lọt lên
    Langfuse mà không có cảnh báo nào. Vì vậy phải gọi hàm này lúc startup,
    trước khi bất kỳ hàm nào có @observe được chạy. Xem init_tracing().
    """
    global _client
    if _client is not None:
        return _client

    if LANGFUSE_SDK_AVAILABLE and tracing_enabled():
        # Không set thì resourceAttributes của trace ghi service.name là
        # "unknown_service" và không lọc được theo service khi nhiều app cùng
        # bắn vào một project. Phải đặt trước khi TracerProvider được dựng.
        os.environ.setdefault(
            "OTEL_SERVICE_NAME", os.getenv("APP_NAME", "day13-observability-lab")
        )
        _client = Langfuse(
            environment=os.getenv("APP_ENV", "dev"),
            release=os.getenv("APP_RELEASE") or None,
            mask=mask_pii,
        )
    else:
        _client = get_client()
    return _client


def init_tracing() -> dict[str, Any]:
    """Khởi tạo client sớm và báo lại trạng thái để log lúc startup.

    Trả về masking_active=False khi mask không gắn được — dấu hiệu client đã bị
    một đường khác khởi tạo trước, và trace sẽ chứa dữ liệu chưa redact.
    """
    client = get_langfuse_client()
    enabled = tracing_enabled()
    resources = getattr(client, "_resources", None)
    masking_active = getattr(resources, "mask", None) is mask_pii
    return {
        "tracing_enabled": enabled,
        "masking_active": masking_active if enabled else None,
        "environment": os.getenv("APP_ENV", "dev"),
    }


def tracing_enabled() -> bool:
    return LANGFUSE_SDK_AVAILABLE and bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )


@contextmanager
def child_span(client: Any, *, name: str, **attributes: Any) -> Iterator[Any]:
    """Span con lồng dưới observation hiện tại; no-op khi client không hỗ trợ."""
    start = getattr(client, "start_as_current_span", None)
    if start is None:
        yield None
        return
    with start(name=name, **attributes) as span:
        yield span


@contextmanager
def child_generation(client: Any, *, name: str, **attributes: Any) -> Iterator[Any]:
    """Generation con lồng dưới observation hiện tại; no-op khi client không hỗ trợ."""
    start = getattr(client, "start_as_current_generation", None)
    if start is None:
        yield None
        return
    with start(name=name, **attributes) as generation:
        yield generation


def update_current_span(client: Any, **attributes: Any) -> None:
    """Gắn attribute lên observation hiện tại; no-op khi client không hỗ trợ.

    Cần cho root span: input/output ở cấp trace không tự chảy xuống observation,
    mà dashboard và evaluator lại đọc input/output của root observation.
    """
    update = getattr(client, "update_current_span", None)
    if update is None:
        return
    update(**attributes)


def score_current_trace(client: Any, *, name: str, value: float, **kwargs: Any) -> None:
    score = getattr(client, "score_current_trace", None)
    if score is None:
        return
    score(name=name, value=value, **kwargs)


def flush(client: Any) -> None:
    """Đẩy nốt buffer trước khi process thoát, nếu không trace cuối sẽ mất."""
    do_flush = getattr(client, "flush", None)
    if do_flush is not None:
        do_flush()
