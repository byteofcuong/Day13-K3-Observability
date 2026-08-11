# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: `<TODO nhóm>`
- Repository URL: `<TODO nhóm>`
- Commit SHA cuối: `<TODO nhóm — lấy bằng git rev-parse HEAD>`
- Thành viên và vai trò: `<TODO nhóm>`

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** — 0 record thiếu field bắt buộc, 0 record thiếu enrichment, 34 correlation ID duy nhất. Output đầy đủ: [evidence/01_validate_logs_output.txt](evidence/01_validate_logs_output.txt).
- Tổng số traces: **40** trên Langfuse (yêu cầu tối thiểu 10).
- Số PII leak còn lại: **0** — kiểm ở hai tầng, `validate_logs.py` cho log và mask hook của Langfuse SDK cho trace.
- Link/đường dẫn dashboard: `streamlit run dashboard/app.py` → http://localhost:8501 (mã nguồn tại `dashboard/app.py`).

## 3. Logging và tracing

- **Evidence correlation ID:** [evidence/06_log_correlation_id.jsonl](evidence/06_log_correlation_id.jsonl) — cặp `request_received`/`response_sent` của cùng `req-1c763513`, đủ metadata `user_id_hash`, `session_id`, `feature`, `model`, `env`. Middleware nhận `x-request-id` từ header nếu có, nếu không thì tự sinh, và trả lại qua header `x-request-id` cùng `x-response-time-ms`.
- **Evidence PII redaction:** [evidence/07_log_pii_redacted.jsonl](evidence/07_log_pii_redacted.jsonl) — các dòng log chứa `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`. Ở phía trace, `f861411d48c24c6d9c1517d32cee563a` có input `{"question": "What is the policy for PII and credit card [REDACTED_CREDIT_CARD]?"}` — chứng minh mask chặn ở cả hai tầng.
- **Evidence trace waterfall:** trace `130a1c3e9726b8bece16c91163cc842c` — 3 observation lồng nhau:

```text
[SPAN]       chat-response       2.656s
  [SPAN]       retrieve-context    2.500s
  [GENERATION] llm-answer          0.152s
```

- **Giải thích một span đáng chú ý:** `retrieve-context` chiếm 2.500s trên tổng 2.656s, tức **94% thời gian** của request. Đây là lý do root observation được để là span chứ không phải generation: nếu cả lượt chat là một generation phẳng thì không tách được thời gian retrieval khỏi thời gian gọi LLM, và không thể chỉ ra thủ phạm.

## 4. Prompt versioning

- **Prompt name:** `day13-chat` (text prompt, giữ đúng ba biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** version 1 — labels `baseline`, `production`.
- **Version/label candidate:** version 2 — label `candidate`, thêm ràng buộc "Trả lời trong tối đa 3 câu và bám sát nội dung trong Docs".
- **Trace ID của mỗi version:**

| Bước | Label dùng | prompt_version ghi trong trace | Trace ID |
|---|---|---|---|
| Chạy với `baseline` | baseline | 1 | `9a15affd991ace0a12027cd58c92c692` |
| Chạy với `candidate` | candidate | 2 | `1699eef51846ef809f67d239fe2eb411` |

- **Bằng chứng đổi label hoặc rollback:** cùng một input, chỉ đổi version mà label `production` trỏ tới:

| Bước | Label | prompt_version | Trace ID |
|---|---|---|---|
| Trước khi đổi | production | 1 | `e5485ed4ae05e17478716b6597b07b0c` |
| Sau khi chuyển `production` → v2 | production | 2 | `8f4a9b8f4f629a0884b6d381790fa9f6` |
| Sau khi rollback `production` → v1 | production | 1 | `d2da8c389562a7ce580a32e5b9bf4ef7` |

Cả 5 trace đều có `prompt_source = langfuse`, không phải `local-fallback` — nghĩa là app thật sự lấy prompt managed chứ không âm thầm dùng template local. Ánh xạ correlation_id ↔ trace ID lưu tại `submission/evidence/label_runs.json`.

## 5. Dashboard, SLO và alerts

- **Kết quả `validate_dashboard.py`:** `HỢP LỆ: 6/6 panel có trong dashboard contract.` Output: [evidence/08_validate_dashboard_output.txt](evidence/08_validate_dashboard_output.txt).
- **Evidence dashboard:** `dashboard/app.py` (Streamlit). Panel không hard-code — tiêu đề, đơn vị, phép tổng hợp và threshold đọc trực tiếp từ `config/dashboard.yaml`, nên dashboard và validator không thể lệch nhau. Percentile dùng lại đúng hàm `app.metrics.percentile` của API để dashboard khớp với `/metrics`. `<TODO nhóm: chụp ảnh dashboard vào submission/evidence/>`
- **SLO đã chọn và lý do:** 4 SLI trong `config/slo.yaml`, mỗi cái có `rationale` giải thích con số. Điểm chính: latency p95 3000ms để target 99.0 chứ không phải 99.5 vì lab chạy trên máy cá nhân và một lần load test cũng đủ đẩy p95 lên; `daily_cost_usd` để target 98.0 vì cost là chỉ tiêu ngân sách chứ không phải cam kết với người dùng; `quality_score_avg` lỏng nhất vì nó là proxy heuristic.
- **Alert rules và runbook:** 3 alert trong `config/alert_rules.yaml`, runbook đầy đủ 8 field trong `docs/alerts.md`. Cả ba đều symptom-based và có thời gian duy trì:

| Alert | Severity | Điều kiện | Bắt incident |
|---|---|---|---|
| ChatResponseTooSlow | P2-high | p95 latency > 3000ms trong 10 phút | `rag_slow` |
| ChatRequestsFailing | P1-critical | error rate > 2% trong 5 phút, tối thiểu 20 request | `tool_fail` |
| DailyCostBudgetBurn | P3-medium | tổng cost 24h > 2.5 USD | `cost_spike` |

## 6. Điều tra challenge

> Challenge chính thức chưa được release. Phần dưới là kết quả chạy incident practice `rag_slow`, dùng đúng luồng Metrics → Traces → Logs sẽ áp dụng cho challenge.

- **Challenge ID:** `<TODO — chờ Lab Coach release config/challenge.json>`
- **Triệu chứng từ metrics:** p95 latency tăng từ **1263ms → 2654ms** sau khi bật `rag_slow` (đọc từ `/metrics`, traffic 10 → 20 request).
- **Trace ID liên quan:** `130a1c3e9726b8bece16c91163cc842c` — span `retrieve-context` chiếm 2.500s trên tổng 2.656s.
- **Log line/correlation ID liên quan:** `req-1c763513`, `event=response_sent`, `latency_ms=2654`, kèm đủ metadata `session_id=s10`, `feature=qa`, `model=claude-sonnet-4-5`, `env=dev`.
- **Root cause:** bước retrieval trong `app/mock_rag.py` chèn `time.sleep(2.5)` khi cờ `rag_slow` bật. Lời gọi LLM vẫn bình thường (0.152s), nên toàn bộ độ trễ đến từ retrieval.
- **Fix action:** tắt cờ incident (`python scripts/inject_incident.py --scenario rag_slow --disable`). Ngoài lab, đặt timeout cho retrieval và fail-open — trả lời không có tài liệu tham chiếu vẫn tốt hơn bắt người dùng chờ.
- **Preventive measure:** alert `ChatResponseTooSlow` với thời gian duy trì 10 phút, cộng với việc tách `retrieve-context` thành span riêng để lần sau khoanh vùng được ngay mà không phải đoán.

### Phát hiện thêm: latency đang bị đo thiếu

Trong lúc điều tra, có một chỗ lệch đáng chú ý. Với 5 request đồng thời khi `rag_slow` đang bật:

| correlation_id | `latency_ms` (agent) | `x-response-time-ms` (middleware) | Chênh lệch |
|---|---|---|---|
| req-fb714f35 | 2652 | 2659 | 7 |
| req-2d1a6d74 | 2653 | 5331 | 2678 |
| req-f61769b6 | 2652 | 7990 | 5338 |
| req-8bf50f09 | 2657 | 10647 | 7990 |
| req-f9dd4437 | 2653 | 10647 | 7994 |

`latency_ms` — con số mà dashboard, SLO và alert đang dùng — chỉ đo phần xử lý bên trong `agent.run`, nên đứng yên ở ~2653ms cho cả 5 request. Trong khi đó thời gian người dùng thật sự chờ lên tới 10647ms, tức **gần 8 giây nằm ở hàng đợi mà không chỉ số nào nhìn thấy**.

Hệ quả trực tiếp: p95 đo được là 2654ms, **vẫn dưới ngưỡng 3000ms**, nên alert `ChatResponseTooSlow` sẽ không kích hoạt dù người dùng đang chờ hơn 10 giây. Đây là ví dụ đúng nghĩa "metric xanh nhưng người dùng vẫn khổ".

Đề xuất: thêm một SLI đo từ middleware (`x-response-time-ms`) thay vì chỉ đo trong agent, và đặt alert trên chỉ số đó. `<TODO nhóm: quyết định có làm trong phạm vi lab hay ghi nhận là việc tiếp theo>`

## 7. Đóng góp cá nhân

`<TODO nhóm: điền bảng dưới, mỗi thành viên một dòng, kèm link commit/PR thật>`

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | | | |
