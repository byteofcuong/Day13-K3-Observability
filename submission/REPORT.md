# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: **K3 — Day13 Observability**
- Repository URL: https://github.com/byteofcuong/Day13-K3-Observability
- Commit SHA cuối: f825b6ce8ec7c64ac7ca665f71fc3f7879736d44
- Thành viên và vai trò:
  - Nguyễn Phú Cường — Metrics, dashboard, SLO và alerting.
  - Nguyễn Hoàng Việt — QA, điều tra incident CP3 và demo Metrics → Traces → Logs.
  - Nguyễn Đông Hùng — nền tảng ứng dụng, PII, prompt/tracing và challenge release.
  - Mai Quốc Hiếu — middleware, correlation ID và gán log metadata.

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** — 231 record, 0 record thiếu field bắt buộc, 0 record thiếu enrichment, 78 correlation ID duy nhất. Output đầy đủ: [evidence/01_validate_logs_output.txt](evidence/01_validate_logs_output.txt).
- Tổng số traces: **50** trong project Langfuse mới `Day13-K3-Observability` tại thời điểm kiểm tra (yêu cầu tối thiểu 10).
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
| Chạy với `baseline` | baseline | 1 | `ee1f7a286279b88ca3f7a61987939506` |
| Chạy với `candidate` | candidate | 2 | `8a541dda6a51b8cc3abf0252f67f2653` |

- **Bằng chứng đổi label hoặc rollback:** cùng một input, chỉ đổi version mà label `production` trỏ tới:

| Bước | Label | prompt_version | Trace ID |
|---|---|---|---|
| Trước khi đổi | production | 1 | `00b711fb6adf09ca830ae86c4a4813b3` |
| Sau khi chuyển `production` → v2 | production | 2 | `9a2047e33a086e950aad63d2fc6e0771` |
| Sau khi rollback `production` → v1 | production | 1 | `07ca01e928b417867757b996385ac8e9` |

Cả 5 trace đều có `prompt_source = langfuse`, không phải `local-fallback` — nghĩa là app thật sự lấy prompt managed chứ không âm thầm dùng template local. Ánh xạ correlation ID ↔ trace ID lưu tại [evidence/label_runs.json](evidence/label_runs.json); trạng thái version/label cuối và chuỗi rollback lưu tại [evidence/prompt-versioning.json](evidence/prompt-versioning.json).

## 5. Dashboard, SLO và alerts

- **Kết quả `validate_dashboard.py`:** `HỢP LỆ: 6/6 panel có trong dashboard contract.` Output: [evidence/08_validate_dashboard_output.txt](evidence/08_validate_dashboard_output.txt).
- **Evidence dashboard:** [evidence/09_dashboard.png.png](evidence/09_dashboard.png.png). Dashboard nằm tại `dashboard/app.py`; tiêu đề, đơn vị, phép tổng hợp và threshold đọc trực tiếp từ `config/dashboard.yaml`. Percentile dùng cùng hàm `app.metrics.percentile` của API để dashboard khớp với `/metrics`.
- **SLO đã chọn và lý do:** 4 SLI trong `config/slo.yaml`, mỗi cái có `rationale` giải thích con số. Điểm chính: latency p95 3000ms để target 99.0 chứ không phải 99.5 vì lab chạy trên máy cá nhân và một lần load test cũng đủ đẩy p95 lên; `daily_cost_usd` để target 98.0 vì cost là chỉ tiêu ngân sách chứ không phải cam kết với người dùng; `quality_score_avg` lỏng nhất vì nó là proxy heuristic.
- **Alert rules và runbook:** 3 alert trong `config/alert_rules.yaml`, runbook đầy đủ 8 field trong `docs/alerts.md`. Cả ba đều symptom-based và có thời gian duy trì:

| Alert | Severity | Điều kiện | Bắt incident |
|---|---|---|---|
| ChatResponseTooSlow | P2-high | p95 latency > 3000ms trong 10 phút | `rag_slow` |
| ChatRequestsFailing | P1-critical | error rate > 2% trong 5 phút, tối thiểu 20 request | `tool_fail` |
| DailyCostBudgetBurn | P3-medium | tổng cost 24h > 2.5 USD | `cost_spike` |

## 6. Điều tra challenge

- **Challenge ID:** `day13-k3-observability-v1` (cohort `K3`, feature bị ảnh hưởng `refund`). Incident được bật bằng `python scripts/inject_incident.py` **không có `--scenario`**; input được chạy bằng `python scripts/load_test.py --challenge --concurrency 5`.
- **Triệu chứng từ metrics:** p95 tăng từ **1680ms lên 2995ms**, vượt ngưỡng challenge **2000ms** thêm 995ms (1,50 lần ngưỡng). Cả 5 request đều HTTP 200, vì vậy đây là sự cố latency chứ không phải error-rate.
- **Trace khoanh vùng:** lọc `feature=refund`, trace `e0a9f1d3c282aec1f7810c09976827e0` cho request `k3-challenge-s03` chỉ ra span bất thường `rag.retrieve=2500ms`, chiếm 61,0% tổng thời gian xử lý `4101ms`.
- **Log chứng minh root cause:** cùng `correlation_id=req-fd08c5e6`, log `rag_retrieval_completed` ghi `trace_id=e0a9f1d3c282aec1f7810c09976827e0`, `span=rag.retrieve`, `latency_ms=2500`, `payload.rag_slow=true`; log `response_sent` ghi `latency_ms=4101`. Chuỗi này nối request → trace → RAG span và chứng minh cờ `rag_slow` chèn 2,5 giây tại retrieval.
- **Fix action:** tắt đúng incident từ challenge bằng `python scripts/inject_incident.py --disable`. Năm request challenge mới có latency xử lý `[1458, 1603, 1593, 533, 1571]ms`, p95 của cửa sổ mới là **1603ms**, thấp hơn 2000ms. `/metrics` vẫn hiện p95 tích lũy 2995ms vì giữ các mẫu trước fix trong bộ nhớ; không dùng con số tích lũy này để tuyên bố recovery.
- **Preventive measure:** đặt alert riêng cho `feature=refund` khi p95 > **2000ms**; theo dõi latency span `rag.retrieve`; đặt timeout/fail-open cho retrieval và đưa endpoint metrics sang cửa sổ trượt để trạng thái recovery không bị mẫu incident cũ che khuất.
- **Phân công CP3:** Nguyễn Hoàng Việt chủ trì điều tra và trình bày chuỗi Metrics → Traces → Logs. Evidence dưới đây được chuẩn bị để Việt tự kiểm chứng và giải thích trực tiếp theo rubric A3.
- **Evidence:** [challenge-metrics.json](evidence/challenge-metrics.json), [challenge-trace.json](evidence/challenge-trace.json), [challenge-log.jsonl](evidence/challenge-log.jsonl).

## 7. Đóng góp cá nhân

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Nguyễn Phú Cường | Metrics, dashboard, SLO, alert rules, evidence CP2 | [commit 5249c27](https://github.com/byteofcuong/Day13-K3-Observability/commit/5249c27), [commit c421923](https://github.com/byteofcuong/Day13-K3-Observability/commit/c421923) | Percentile phải khớp giữa API và dashboard; alert cần condition, duration, severity và owner rõ ràng. |
| Nguyễn Hoàng Việt | Chủ trì CP3; điều tra Metrics → Traces → Logs; fix và preventive measure | [commit 55e10dc](https://github.com/byteofcuong/Day13-K3-Observability/commit/697df60a52866ed656a2b816497a5b1f403cdad2) | Correlation ID nối trace với log; phải dùng ngưỡng 2000ms và lọc `feature=refund` của challenge. |
| Nguyễn Đông Hùng | Khởi tạo app, PII redaction, prompt/tracing và challenge config | [commit f1a02e5](https://github.com/viett207/Day13-K3-Observability/commit/f1a02e5087e90e9105261402f369be523e75404b), [commit 7a57bfb](https://github.com/viett207/Day13-K3-Observability/commit/7a57bfb239f83d8246c1264d0b08f95d3d22b5d2) | Trace cần metadata/version; PII phải được chặn ở cả log và exporter. |
| Mai Quốc Hiếu | Middleware, correlation ID, log metadata, PII scrubbing và metrics calculation | [commit 6c9be68](https://github.com/byteofcuong/Day13-K3-Observability/commit/6c9be6876459986c0eb5c8c3683ed8ac38e71ea0) | Correlation ID phải được truyền xuyên suốt request/response; metadata cần nhất quán và PII phải được redact trước khi ghi log. |
