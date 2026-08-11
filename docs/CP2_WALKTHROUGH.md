# Checkpoint 2 — Walkthrough

**1:30–2:30 · 60 phút · Metrics, traces, prompt versioning và dashboard**

Đây là mốc nặng điểm nhất: 20 trên 30 điểm của phần A1 nằm ở đây (bullet 2 và bullet 3 trong [RUBRIC.md](../RUBRIC.md)).

---

## Hai thứ đang chặn

### 1. Langfuse key đang rỗng — chặn cứng

`LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY` trong `.env` đều chưa có giá trị. Khi đó `tracing_enabled()` trong [app/tracing.py](../app/tracing.py) trả `False`, không trace nào được gửi lên Langfuse và prompt luôn rơi về `prompt_source=local`.

**Hệ quả:** mất trọn 10 điểm "traces đầy đủ; prompt v1/v2 có label, version metadata và bằng chứng rollback". Không có cách vòng qua — xin key từ Lab Coach hoặc tạo project trên Langfuse Cloud ngay.

### 2. Correlation ID chưa hoạt động — chờ CP1

[app/middleware.py](../app/middleware.py) đang hard-code `correlation_id = "MISSING"` và `bind_contextvars` vẫn bị comment, nên log chưa có correlation ID để nối với trace.

**Chỉ chặn đúng một bước** — bước B2 bên dưới. Toàn bộ track A chạy được ngay bây giờ, vì `"MISSING"` là giá trị hard-code chứ không làm app crash.

---

## Track A — làm ngay (~45 phút, không phụ thuộc đồng đội)

### A1. Bật tracing và xác nhận — 5 phút

Điền key vào `.env`, rồi khởi động API và kiểm tra health.

```bash
uvicorn app.main:app --reload --env-file .env

# terminal khác
curl http://127.0.0.1:8000/health
```

Kết quả phải có `"tracing_enabled": true`. Nếu vẫn `false`, key chưa được nạp — kiểm tra lại `.env` và restart uvicorn.

> **Lưu ý:** `--env-file` chỉ đọc `.env` lúc khởi động. Mọi lần sửa `.env` ở các bước sau đều phải restart API.

### A2. Tạo prompt v1 và v2 trên Langfuse — 10 phút

Tạo một *text prompt* tên đúng bằng `day13-chat` (khớp `LANGFUSE_PROMPT_NAME`). Nội dung v1 phải giữ nguyên đủ ba biến:

```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

> **Đây là chỗ dễ mất điểm nhất.** App gọi `.compile(feature=…, docs=…, message=…)` tại [app/prompt_management.py:62-66](../app/prompt_management.py#L62-L66). Nếu prompt thiếu hoặc đặt sai tên một biến, lệnh compile ném exception, app nuốt lỗi và ghi `prompt_source=local-fallback` — trace trông vẫn "có" nhưng không tính là dùng prompt managed.

- **v1**: gắn **hai** label `baseline` và `production`.
- **v2**: sửa nhỏ về format hoặc độ dài (ví dụ thêm dòng *"Trả lời trong tối đa 3 câu."*), gắn label `candidate`. Vẫn phải giữ đủ ba biến.

Không ai chấm prompt nào hay hơn — điểm nằm ở khả năng truy xuất version và đổi label.

### A3. Sinh traces và lấy 2 trace ID cho 2 version — 10 phút

`data/sample_queries.jsonl` có **đúng 10 dòng**, nên một lần chạy cho đúng 10 trace — vừa sát ngưỡng "tối thiểu 10". Chạy hai lần cho chắc.

```bash
python scripts/load_test.py
python scripts/load_test.py
```

Sau đó chạy cùng một input với hai label khác nhau để có hai trace so sánh:

1. Đặt `LANGFUSE_PROMPT_LABEL=baseline` → restart API → chạy 1 request → lưu trace ID.
2. Đặt `LANGFUSE_PROMPT_LABEL=candidate` → restart API → chạy *đúng input đó* → lưu trace ID.

Mở cả hai trace, xác nhận metadata có `prompt_name`, `prompt_label`, `prompt_version` và **`prompt_source` phải là `langfuse`**. Thấy `local-fallback` là quay lại A2.

> **Cache 60 giây.** Prompt được cache `cache_ttl_seconds=60`, nên sau khi đổi label trên Langfuse hãy chờ hơn 60 giây hoặc restart API trước khi chạy request tiếp theo.

### A4. Đổi label và rollback, chụp trước – sau — 5 phút

1. Chụp trạng thái hiện tại: `production` đang trỏ v1.
2. Chuyển `production` sang v2 → restart API → chạy 1 request → chụp trace hiển thị `prompt_version` là 2.
3. Rollback `production` về v1 → restart API → chạy 1 request → chụp trace hiển thị version 1.

Ba ảnh này chính là "bằng chứng rollback" trong rubric. Lưu vào `submission/evidence/`.

### A5. Dashboard 6 panel — ĐÃ XONG

Dashboard Streamlit nằm ở [`dashboard/app.py`](../dashboard/app.py):

```bash
python scripts/validate_dashboard.py     # HỢP LỆ: 6/6 panel
streamlit run dashboard/app.py           # http://localhost:8501
```

Panel không hard-code: tiêu đề, đơn vị, phép tổng hợp và threshold đều đọc từ `config/dashboard.yaml`, nên dashboard và validator luôn nói về cùng một contract. Percentile dùng lại đúng hàm `app.metrics.percentile` của API để dashboard không lệch với `/metrics`.

Việc còn lại của bạn: chạy load test cho đủ dữ liệu rồi **chụp ảnh evidence** (nên chụp sau khi CP1 merge, xem B3). Sáu panel khớp contract như sau:

| Panel | Field trong log | Tổng hợp | Threshold |
|---|---|---|---|
| latency | `response_sent.latency_ms` | p50, p95, p99 | p95 ≤ 3000 ms |
| traffic | `request_received` | count, req/phút | ≥ 1 req/phút |
| errors | `error_type` | error rate, breakdown | ≤ 2 % |
| cost | `response_sent.cost_usd` | sum theo phút, tổng | tổng ≤ 2.5 USD |
| tokens | `tokens_in`, `tokens_out` | sum từng field | ≤ 50 000 tokens |
| quality | `response_sent.quality_score` | mean | ≥ 0.75 |

Giữ time range 60 phút, refresh 30 giây, và vẽ threshold/SLO line nhìn thấy được. Ảnh evidence phải đọc được tên panel, time range, đơn vị và threshold.

> **Không cần chờ CP1.** Sáu panel này dùng `latency_ms`, `cost_usd`, `tokens_*`, `quality_score`, `error_type` — không cái nào nằm trong năm field mà CP1 đang bổ sung (`user_id_hash`, `session_id`, `feature`, `model`, `env`).

### A6. SLO, 3 alert rule và runbook — ĐÃ XONG

Ba file đã điền, `grep -rn "TODO" config/` không còn kết quả:

- [`config/slo.yaml`](../config/slo.yaml) — 4 SLI với target, error budget và lý do chọn từng con số.
- [`config/alert_rules.yaml`](../config/alert_rules.yaml) — 3 alert symptom-based, mỗi cái có thời gian duy trì.
- [`docs/alerts.md`](alerts.md) — runbook đủ 8 field mỗi alert; anchor `#alert-1/2/3` giữ nguyên nên `runbook` trong YAML vẫn trỏ đúng.

Ba alert phủ đúng ba incident practice trong `app/incidents.py`, nên demo CP3 nối thẳng được:

| Alert | Severity | Bắt incident |
|---|---|---|
| ChatResponseTooSlow | P2-high | `rag_slow` |
| ChatRequestsFailing | P1-critical | `tool_fail` |
| DailyCostBudgetBurn | P3-medium | `cost_spike` |

**Một việc bạn phải tự làm:** `owner` đang ghi theo vai trò (`Tracing & Prompt Version`…). Đổi thành tên người thật trước khi nộp.

---

## Track B — cần CP1 xong (~15 phút)

**Tín hiệu để bắt đầu:** đồng đội báo `python scripts/validate_logs.py` đạt ≥ 80/100, và một dòng trong `data/logs.jsonl` có `correlation_id` dạng `req-xxxxxxxx` thay vì `MISSING`.

### B1. Sinh lại log sạch

Xoá `data/logs.jsonl` cũ rồi chạy lại load test, để log mới có đủ metadata và đã redact PII.

> **Trước khi CP1 xong, đừng chụp ảnh log line làm evidence.** Processor `scrub_event` vẫn đang bị comment trong `configure_logging()` tại [app/logging_config.py:45-46](../app/logging_config.py#L45-L46), nên log hiện tại chứa nguyên văn email và số điện thoại từ `sample_queries.jsonl`. File đã nằm trong `.gitignore` nên không lọt vào Git, nhưng ảnh chụp thì có.

### B2. Runtime check: metrics → trace → log

Đây là bước duy nhất thật sự cần correlation ID, và cũng là bài tập dượt cho challenge ở CP3.

```bash
# 1. ghi lại baseline: p95, error rate, cost hiện tại
python scripts/load_test.py --concurrency 5

# 2. bật incident practice
python scripts/inject_incident.py --scenario rag_slow
python scripts/load_test.py --concurrency 5

# 3. tắt sau khi đã chụp evidence
python scripts/inject_incident.py --scenario rag_slow --disable
```

1. Xác nhận panel latency có p95 tăng rõ rệt so với baseline.
2. Mở trace chậm nhất trên Langfuse, xem span nào ăn thời gian.
3. Tìm log line có **cùng correlation ID** với trace đó — đây là mắt xích CP1 cung cấp.

### B3. Chụp ảnh evidence cuối và ghi vào report

Chụp lại dashboard sau khi log đã đủ metadata, lưu tất cả vào `submission/evidence/`, rồi điền đường dẫn tương đối vào `submission/REPORT.md`:

- **Mục 4 — Prompt versioning:** prompt name, version/label baseline và candidate, hai trace ID, bằng chứng rollback.
- **Mục 5 — Dashboard, SLO và alerts:** kết quả validator, ảnh dashboard, SLO đã chọn kèm lý do, alert rules và runbook.

---

## Tiêu chí hoàn thành CP2

Chín mục dưới đây gộp yêu cầu của [CHECKPOINTS.md](../CHECKPOINTS.md) và [docs/grading-evidence.md](grading-evidence.md). Thiếu bất kỳ mục nào là mất điểm ở A1.

| # | Tiêu chí | Cách xác nhận | Bước |
|---|---|---|---|
| 01 | Có tối thiểu 10 trace kèm metadata trên Langfuse | 2 lần `load_test.py` = 20 trace | A3 |
| 02 | Trace hiển thị đủ `prompt_name`, `prompt_label`, `prompt_version` | và `prompt_source` = `langfuse`, không phải `local-fallback` | A3 |
| 03 | Prompt `day13-chat` có 2 version với label khác nhau | v1 = `baseline` + `production` · v2 = `candidate` | A2 |
| 04 | Một thao tác đổi label hoặc rollback có ảnh trước – sau | 3 ảnh: production→v1, production→v2, rollback→v1 | A4 |
| 05 | ✅ Validator dashboard chạy sạch | `validate_dashboard.py` → `HỢP LỆ: 6/6 panel` | A5 |
| 06 | ✅ Dashboard runtime đủ 6 panel, đọc được tên/đơn vị/threshold | `streamlit run dashboard/app.py` · còn thiếu **ảnh evidence** | A5 |
| 07 | ✅ SLO line hoặc threshold thể hiện rõ trên dashboard | `config/slo.yaml` đã thay target mặc định | A6 |
| 08 | ✅ 3 alert rule và runbook hoàn thiện | `grep -rn "TODO" config/` không còn kết quả · còn phải đổi `owner` sang tên thật | A6 |
| 09 | Evidence nằm trong `submission/evidence/` và được dẫn lại trong report | đường dẫn tương đối · `REPORT.md` mục 4 và mục 5 | B3 |

Lệnh chốt cuối checkpoint:

```bash
python scripts/validate_dashboard.py
python -m pytest -q
grep -rn "TODO" config/
```
