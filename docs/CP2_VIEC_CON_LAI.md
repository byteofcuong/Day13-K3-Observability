# Việc còn lại — CP1 và CP2

Phần kỹ thuật đã xong và kiểm chứng được. Còn lại **5 việc**, ước tính **25–30 phút**, tất cả đều cần con người làm.

Định nghĩa "xong" của CP2 nằm ở [CHECKPOINTS.md](../CHECKPOINTS.md): *"Chụp hai trace prompt, thao tác rollback, kết quả validator và dashboard vào `submission/evidence/`"*.

---

## Việc 0 — 2 ảnh còn thiếu của CP1 (~4 phút)

Đề bài trên Codelabs yêu cầu CP1 nộp **ảnh chụp màn hình**, không phải file text:

> *"Ảnh chụp màn hình điểm log validator và một đoạn log chứa correlation ID kèm chuỗi che thông tin `[REDACTED_...]` lưu trong thư mục `submission/evidence/`"*

Các file `.txt`/`.jsonl` đã có trong `submission/evidence/` là bổ trợ tốt (giám khảo grep được), nhưng **không thay thế được ảnh**.

### Ảnh A — điểm validator

```bash
python scripts/validate_logs.py
```

- **Khung ảnh phải thấy:** dòng `Estimated Score: 100/100` và 4 dòng `[PASSED]` phía trên.
- **Lưu:** `submission/evidence/A_validate_logs_score.png`

### Ảnh B — log có correlation ID + `[REDACTED_...]`

```bash
python scripts/show_log_evidence.py
```

Script này lọc sẵn những bản ghi thoả **cả hai** điều kiện cùng lúc, nên một ảnh là đủ cho cả yêu cầu correlation ID lẫn yêu cầu redaction.

- **Khung ảnh phải thấy:** `correlation_id: req-xxxxxxxx`, đủ 5 field metadata (`user_id_hash`, `session_id`, `feature`, `model`, `env`), và chuỗi `[REDACTED_EMAIL]` / `[REDACTED_PHONE_VN]` / `[REDACTED_CREDIT_CARD]`.
- **Lưu:** `submission/evidence/B_log_correlation_pii.png`

> Ảnh B tiện thể chứng minh luôn `env` — field mà `validate_logs.py` **không** kiểm (`ENRICHMENT_FIELDS` ở [scripts/validate_logs.py:8](../scripts/validate_logs.py#L8) chỉ có 4 field), trong khi CP1 yêu cầu 5.

---

## Trạng thái evidence

| # | Evidence | Trạng thái |
|---|---|---|
| A | **CP1** — ảnh điểm log validator | ⬜ **cần ảnh** |
| B | **CP1** — ảnh log có correlation ID + `[REDACTED_...]` | ⬜ **cần ảnh** |
| 01 | Kết quả `validate_logs.py` (bản text bổ trợ) | ✅ `evidence/01_validate_logs_output.txt` |
| 02 | Danh sách ≥10 traces | ⬜ **cần ảnh** |
| 03 | Một trace waterfall | ⬜ **cần ảnh** |
| 04 | Hai prompt version + trace gắn đúng version/label | ⬜ **cần ảnh** |
| 05 | Bằng chứng đổi label / rollback | ⬜ **cần ảnh** |
| 06 | Log có correlation ID + metadata | ✅ `evidence/06_log_correlation_id.jsonl` |
| 07 | Log chứng minh PII đã redact | ✅ `evidence/07_log_pii_redacted.jsonl` |
| 08 | Kết quả `validate_dashboard.py` | ✅ `evidence/08_validate_dashboard_output.txt` |
| 09 | Dashboard đủ 6 nhóm chỉ số | ⬜ **cần ảnh** |
| — | Ánh xạ correlation_id ↔ trace ID | ✅ `evidence/label_runs.json` |

---

## Việc 1 — Chụp 5 ảnh (~15 phút)

Project Langfuse: `My Project`
Base URL: `https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8`

Lưu tất cả vào `submission/evidence/` **đúng tên file** dưới đây, vì report đã dẫn sẵn theo tên này.

### Ảnh 02 — danh sách traces

- **Mở:** https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/traces
- **Khung ảnh phải thấy:** tổng số trace (40), cột `Name` toàn `chat-response`, cột timestamp.
- **Lưu:** `submission/evidence/02_traces_list.png`

### Ảnh 03 — trace waterfall

- **Mở:** https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/traces/130a1c3e9726b8bece16c91163cc842c
- **Khung ảnh phải thấy:** cây 3 tầng `chat-response` → (`retrieve-context`, `llm-answer`) và **thanh thời lượng**, trong đó `retrieve-context` chiếm 2.500s / 2.656s.
- **Vì sao chọn trace này:** nó là trace chậm nhất lúc bật `rag_slow`, nên waterfall nhìn ra ngay thủ phạm. Đây cũng là trace đã dẫn ở mục 3 và mục 6 của report.
- **Lưu:** `submission/evidence/03_trace_waterfall.png`

### Ảnh 04 — hai prompt version

- **Mở:** https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/prompts/day13-chat
- **Khung ảnh phải thấy:** cả version 1 và version 2, cùng các label `baseline` / `production` / `candidate`.
- **Lưu:** `submission/evidence/04_prompt_versions.png`

Chụp thêm **một** trong hai trace dưới để chứng minh trace gắn đúng version (mở tab `Metadata`, thấy `prompt_name`, `prompt_label`, `prompt_version`, `prompt_source: langfuse`):

| Label | Version | Link |
|---|---|---|
| baseline | 1 | https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/traces/9a15affd991ace0a12027cd58c92c692 |
| candidate | 2 | https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/traces/1699eef51846ef809f67d239fe2eb411 |

- **Lưu:** `submission/evidence/04b_trace_prompt_metadata.png`

### Ảnh 05 — rollback

Ba trace dưới cùng một input, chỉ khác version mà label `production` trỏ tới. Chụp **metadata của cả ba** (ghép một ảnh hoặc ba ảnh đều được):

| Bước | prompt_version | Link |
|---|---|---|
| Trước khi đổi | 1 | https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/traces/e5485ed4ae05e17478716b6597b07b0c |
| Chuyển `production` → v2 | 2 | https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/traces/8f4a9b8f4f629a0884b6d381790fa9f6 |
| Rollback `production` → v1 | 1 | https://cloud.langfuse.com/project/cmso3v73i043xad0jo6cc99h8/traces/d2da8c389562a7ce580a32e5b9bf4ef7 |

- **Lưu:** `submission/evidence/05_rollback.png`

Điểm cần thấy rõ trong ảnh: `prompt_label` **luôn là `production`** ở cả ba, chỉ `prompt_version` đổi 1 → 2 → 1. Đó mới là bằng chứng rollback, không phải chỉ đổi label khi gọi.

### Ảnh 09 — dashboard

```bash
# terminal 1
uvicorn app.main:app --port 8000 --env-file .env

# terminal 2 — sinh dữ liệu tươi trong cửa sổ 60 phút
python scripts/load_test.py
python scripts/load_test.py

# terminal 3
streamlit run dashboard/app.py
```

- **Mở:** http://localhost:8501
- **Khung ảnh phải thấy:** đủ **6 panel**, dòng caption `Time range 60 phút · Refresh 30s`, đơn vị trên từng tile, và **đường threshold nét đứt màu đỏ** trên các chart.
- **Bắt buộc:** checkbox `Bỏ qua time range (debug)` ở sidebar phải **TẮT**. Nếu bật, dashboard hiện cảnh báo vàng và ảnh sẽ không dùng làm evidence được.
- **Nếu panel trống:** log cũ hơn 60 phút — chạy lại `load_test.py` rồi chụp.
- **Lưu:** `submission/evidence/09_dashboard.png`

> Lưu ý: tôi mới verify dashboard bằng `AppTest` (chạy không lỗi, threshold đúng), **chưa nhìn bằng mắt trong browser**. Bạn là người đầu tiên nhìn thấy nó — nếu chart hay đường threshold trông sai, báo tôi sửa.

---

## Việc 2 — Đổi `owner` sang tên thật (~2 phút)

Trong [config/alert_rules.yaml](../config/alert_rules.yaml), 3 dòng `owner` đang ghi tên vai trò:

```yaml
owner: Tracing & Prompt Version      # dòng 14
owner: Incident, Report & Demo       # dòng 21
owner: Dashboard, SLO & Alert        # dòng 28
```

Đổi thành tên người thật trong nhóm. Cột owner mà không có người cụ thể thì lúc chấm coi như chưa hoàn thiện.

Sau khi sửa, xoá luôn đoạn ghi chú tương ứng ở cuối [docs/alerts.md](alerts.md) ("`owner` đang ghi theo **vai trò**...").

---

## Việc 3 — Điền `submission/REPORT.md` (~5 phút)

Còn 3 chỗ `<TODO nhóm>` thuộc phạm vi CP2 hoặc chung:

| Mục | Cần điền |
|---|---|
| 1. Thông tin nhóm | tên nhóm, repo URL, commit SHA cuối, thành viên + vai trò |
| 5. Evidence dashboard | thay `<TODO nhóm: chụp ảnh...>` bằng `![dashboard](evidence/09_dashboard.png)` |
| 7. Đóng góp cá nhân | mỗi thành viên một dòng, kèm link commit/PR thật |

Sau khi có đủ 5 ảnh, thêm link vào các mục tương ứng theo **đường dẫn tương đối** (ví dụ `![waterfall](evidence/03_trace_waterfall.png)`) — [grading-evidence.md](grading-evidence.md) yêu cầu đúng dạng này.

Mục 6 còn một câu hỏi cần nhóm quyết định: có thêm SLI đo từ `x-response-time-ms` trong phạm vi lab không, hay ghi nhận là việc tiếp theo. Trả lời một câu là đủ.

---

## Việc 4 — Commit (~3 phút)

Đang có 4 thay đổi chưa commit:

```text
M app/agent.py           # sửa sau self-audit: input/output cho root span
M app/tracing.py         # sửa sau self-audit: OTEL_SERVICE_NAME + update_current_span
M submission/REPORT.md
?? submission/evidence/  # các file evidence
```

Tôi cố ý **không commit** vì rubric B2 chấm đóng góp cá nhân theo authorship — người làm phần nào nên đứng tên commit phần đó.

```bash
git add -A
git commit -m "..."      # ghi rõ ai làm gì
git rev-parse HEAD       # lấy SHA điền vào REPORT.md mục 1
```

Kiểm tra trước khi commit: `git status --short` không được thấy `.env`. (Đã có trong `.gitignore`, nhưng SUBMISSION.md liệt kê lộ secret là lỗi khiến bài không hợp lệ.)

---

## Chốt CP2

```bash
python -m pytest -q                     # ky vọng 24 passed
python scripts/validate_dashboard.py    # HỢP LỆ: 6/6 panel
python scripts/validate_logs.py         # 100/100
grep -rn "TODO" config/                 # không còn kết quả
ls submission/evidence/                 # đủ 5 ảnh + 4 file text + label_runs.json
```

Xong 4 việc trên là CP2 đóng. CP3 phải chờ Lab Coach release `config/challenge.json`.
