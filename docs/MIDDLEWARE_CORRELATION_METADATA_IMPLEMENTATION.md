# Tri?n khai Middleware, Correlation ID v? Log Metadata

## Ph?m vi ?? ho?n th?nh

?? ho?n th?nh ba ph?n c?a checkpoint Logging & PII li?n quan ??n request context:

1. Middleware t?o v? truy?n correlation ID.
2. Correlation ID xu?t hi?n xuy?n su?t request, response v? log.
3. Log API ???c g?n metadata c?a request theo context c?a `structlog`.

Ph?n PII scrubbing trong `app/logging_config.py` l? TODO ri?ng v? kh?ng ???c thay ??i trong l?n tri?n khai n?y.

## C?c file ?? thay ??i

| File | Thay ??i |
| --- | --- |
| `app/middleware.py` | Ho?n thi?n `CorrelationIdMiddleware`. |
| `app/main.py` | Bind metadata tr??c khi t?o log ??u ti?n c?a `/chat`. |
| `tests/test_middleware.py` | Th?m test cho middleware v? metadata. |

## Lu?ng x? l? request

```text
HTTP request
  -> CorrelationIdMiddleware
     -> clear context c?
     -> l?y x-request-id ho?c sinh req-<8 k? t? hex>
     -> bind correlation_id v?o structlog
     -> l?u request.state.correlation_id
  -> endpoint /chat
     -> bind user_id_hash, session_id, feature, model, env
     -> request_received / agent.run / response_sent
  -> middleware th?m x-request-id v? x-response-time-ms v?o response
  -> clear context khi request k?t th?c
```

## Correlation ID

Middleware ?u ti?n header `x-request-id` ?? gi? ???c li?n k?t khi request ?? ?i qua gateway ho?c service kh?c. N?u header kh?ng t?n t?i, r?ng, ho?c c? gi? tr? `MISSING`, middleware sinh m?t ID m?i c? d?ng `req-xxxxxxxx` b?ng `uuid.uuid4().hex[:8]`.

Correlation ID ???c g?n theo hai c?ch:

- `bind_contextvars(correlation_id=...)`: `merge_contextvars` trong logging config t? th?m ID n?y v?o log.
- `request.state.correlation_id`: endpoint `/chat` d?ng ID n?y ?? tr? trong JSON response.

Response c?ng tr? hai header:

- `x-request-id`: correlation ID c?a request.
- `x-response-time-ms`: t?ng th?i gian middleware x? l? request, t?nh b?ng milliseconds.

`clear_contextvars()` ???c g?i ? ??u v? cu?i request. ?i?u n?y ng?n metadata c?a request tr??c xu?t hi?n nh?m trong request sau.

## Metadata ???c g?n cho log /chat

Metadata ???c bind tr??c s? ki?n `request_received`, n?n s? t? ?i k?m m?i log sau ?? trong c?ng request, g?m `request_received`, `response_sent` v? `request_failed`.

| Field | Gi? tr? | L? do |
| --- | --- | --- |
| `user_id_hash` | `hash_user_id(body.user_id)` | Kh?ng ghi user ID nguy?n b?n v?o log. |
| `session_id` | `body.session_id` | Gom c?c request c?ng phi?n. |
| `feature` | `body.feature` | Ph?n t?ch theo t?nh n?ng, v? d? `qa`. |
| `model` | `agent.model` | Bi?t model ?? ph?c v? request m? kh?ng hard-code. |
| `env` | `APP_ENV`, m?c ??nh `dev` | Ph?n bi?t log m?i tr??ng. |

`correlation_id` ???c middleware bind tr??c ??, do ?? kh?ng c?n bind l?i trong endpoint.

## Ki?m th? ?? th?m

`tests/test_middleware.py` ki?m tra:

1. `/health` nh?n correlation ID m?i ??ng ??nh d?ng v? c? `x-response-time-ms`.
2. `/chat` gi? nguy?n `x-request-id` t? client.
3. JSON response v? header response tr? c?ng correlation ID.
4. C?c log `service=api` c? chung correlation ID.
5. Log c? ?? `user_id_hash`, `session_id`, `feature`, `model`, `env`.
6. `user_id_hash` kh?ng b?ng raw `user_id`.

## C?ch t? ki?m tra

Ch?y test:

```powershell
python -m pytest -q tests/test_middleware.py tests/test_chat_observability.py
```

Sau khi ch?y API v? g?i nhi?u request `/chat`, ch?y validator:

```powershell
python scripts/validate_logs.py
```

C?c log API c?n c? `correlation_id` kh?c `MISSING`, c?ng v?i `user_id_hash`, `session_id`, `feature` v? `model`. ?? checkpoint Logging & PII ??t tr?n v?n, nh?m v?n c?n b?t PII processor ri?ng trong `app/logging_config.py` v? ki?m tra kh?ng c?n d? li?u nh?y c?m trong file log.

