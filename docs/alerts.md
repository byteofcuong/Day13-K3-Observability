# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

Định nghĩa máy đọc nằm ở [`config/alert_rules.yaml`](../config/alert_rules.yaml); ngưỡng lấy từ [`config/slo.yaml`](../config/slo.yaml) và phải khớp threshold trong [`config/dashboard.yaml`](../config/dashboard.yaml). Ba file này lệch nhau là dấu hiệu contract đã hỏng.

Tiêu đề `## Alert 1/2/3` giữ nguyên để anchor `#alert-1/2/3` trong YAML còn trỏ đúng.

## Alert 1

- **Tên:** ChatResponseTooSlow
- **Severity:** P2-high — người dùng vẫn nhận được câu trả lời, chỉ là chậm.
- **SLI/SLO liên quan:** `latency_p95_ms` — objective 3000ms, target 99.0% trong 28 ngày.
- **Điều kiện và thời gian duy trì:** p95 của `response_sent.latency_ms` vượt 3000ms **liên tục 10 phút**. Dùng 10 phút vì một lần load test `--concurrency 5` cũng đẩy p95 lên vài chục giây nhưng tự hết.
- **Ảnh hưởng tới người dùng:** câu trả lời mất hơn 3 giây, người dùng bắt đầu bỏ ngang hoặc bấm gửi lại — làm tải tăng thêm và khuếch đại chính sự cố.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở panel `latency` trên dashboard, xác nhận p95 tăng thật chứ không phải một outlier kéo p99.
  2. Mở trace chậm nhất trên Langfuse, so thời lượng span `retrieve-context` với `llm-answer` — đây là lý do hai bước được tách span riêng.
  3. Lấy `correlation_id` của trace đó, tìm log line tương ứng trong `data/logs.jsonl` để xác nhận triệu chứng và khoanh thời điểm bắt đầu.
- **Mitigation tạm thời:** nếu `retrieve-context` là thủ phạm, tắt incident đang bật bằng `python scripts/inject_incident.py --scenario rag_slow --disable`; ngoài lab thì hạ timeout retrieval và trả lời bằng fallback không có RAG thay vì để người dùng chờ.
- **Owner:** Tracing & Prompt Version

## Alert 2

- **Tên:** ChatRequestsFailing
- **Severity:** P1-critical — người dùng mất hẳn câu trả lời, không phải chỉ chờ lâu.
- **SLI/SLO liên quan:** `error_rate_pct` — objective 2%, target 99.0% trong 28 ngày.
- **Điều kiện và thời gian duy trì:** `count(request_failed) / count(request_received)` vượt 2% **liên tục 5 phút**, và chỉ tính khi đã có **ít nhất 20 request** trong cửa sổ. Không có điều kiện số lượng tối thiểu thì 1 lỗi trên 3 request lúc vắng traffic đã thành 33% và page giả.
- **Ảnh hưởng tới người dùng:** request trả HTTP 500, người dùng không nhận được gì. Thời gian duy trì ngắn nhất trong ba alert vì đây là mức nghiêm trọng nhất.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở panel `errors`, đọc breakdown theo `error_type` — một loại lỗi áp đảo nghĩa là một nguyên nhân, phân tán đều nghĩa là hạ tầng.
  2. Lọc log `event == "request_failed"` trong `data/logs.jsonl`, lấy `payload.detail` của vài dòng gần nhất.
  3. Kiểm tra `GET /health` xem incident nào đang bật; `tool_fail` làm `retrieve()` ném `RuntimeError("Vector store timeout")`.
- **Mitigation tạm thời:** tắt incident bằng `python scripts/inject_incident.py --scenario tool_fail --disable`; ngoài lab thì cho retrieval fail-open — trả lời không có tài liệu tham chiếu vẫn tốt hơn trả 500.
- **Owner:** Incident, Report & Demo

## Alert 3

- **Tên:** DailyCostBudgetBurn
- **Severity:** P3-medium — không ai bị ảnh hưởng ngay, nhưng tiền vẫn đang chảy.
- **SLI/SLO liên quan:** `daily_cost_usd` — objective 2.5 USD/ngày, target 98.0%.
- **Điều kiện và thời gian duy trì:** tổng `response_sent.cost_usd` trong **cửa sổ trượt 24 giờ** vượt 2.5 USD. Không cần điều kiện duy trì vì bản thân phép cộng 24h đã đủ làm mượt.
- **Ảnh hưởng tới người dùng:** không trực tiếp. Ảnh hưởng là ngân sách, và thường là triệu chứng gián tiếp của lỗi khác — retry loop, prompt phình to sau khi đổi version, hoặc traffic bất thường.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở panel `cost` và `tokens`: cost tăng mà traffic phẳng thì vấn đề nằm ở số token mỗi request, không phải số request.
  2. Nếu token mỗi request tăng, kiểm tra `prompt_version` và `prompt_label` trong metadata trace — một lần đổi label `production` sang prompt dài hơn là nghi phạm đầu tiên.
  3. Đối chiếu panel `traffic` để loại trừ khả năng chỉ là chạy load test.
- **Mitigation tạm thời:** rollback label `production` về version trước theo [PROMPT_VERSIONING.md](PROMPT_VERSIONING.md), rồi chạy lại một request để xác nhận token/request trở lại mức cũ. Với `cost_spike`, tắt bằng `python scripts/inject_incident.py --scenario cost_spike --disable`.
- **Owner:** Dashboard, SLO & Alert

## Ghi chú khi bàn giao

`owner` đang ghi theo **vai trò** trong nhóm. Trước khi nộp, đổi thành tên người thật để cột owner có nghĩa lúc chấm.

Không có alert riêng cho `quality_score`: nó là proxy heuristic, và một alert dựa trên proxy sẽ tạo nhiều page giả hơn là phát hiện thật. Chỉ tiêu này vẫn có threshold trên dashboard và vẫn nằm trong `slo.yaml` để theo dõi xu hướng.
