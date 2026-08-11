# Checklist cuối trước khi nộp

## Đã hoàn tất và kiểm chứng

- `python -m pytest -q`: 24 test đạt.
- `python scripts/validate_logs.py`: 100/100; 231 record; 78 correlation ID; 0 PII leak.
- `python scripts/validate_dashboard.py`: 6/6 panel hợp lệ.
- Project Langfuse mới có 50 trace tại thời điểm kiểm tra, vượt yêu cầu tối thiểu 10; trace challenge mới đã có trên API.
- Prompt `day13-chat` có v1/v2; `baseline`, `candidate`, `production` đã được kiểm chứng bằng 5 trace thật; `production` đã rollback về v1.
- CP3 có evidence metric, trace và log trong `submission/evidence/`.
- `.env` bị gitignore và không được Git theo dõi.
- `config/challenge.json` không bị sửa.

## BẠN CẦN LÀM trước khi nộp

1. Xác nhận repository cuối dùng để nộp. Workspace hiện trỏ tới `https://github.com/byteofcuong/Day13-K3-Observability`; nếu nộp fork `viett207`, thay URL trong report.
2. Xác nhận danh sách thành viên, vai trò và nội dung đóng góp cá nhân. Mỗi link commit phải mở được khi đăng xuất GitHub.
3. Chụp danh sách prompt v1/v2 và trạng thái rollback trên project Langfuse mới, thay hai ảnh `04_prompt_versions.png.png` và `05_rollback.png.png`. Evidence JSON và 5 trace mới đã hoàn tất.
4. Chụp waterfall của trace challenge mới `e0a9f1d3c282aec1f7810c09976827e0` sau khi Langfuse v4 index xong, rồi thay ảnh trace waterfall hiện có. JSON/log evidence và report đã dùng trace mới này.
5. Chụp/kiểm tra ảnh không lộ secret hoặc PII. Không đưa `.env` vào Git.
6. Commit và push toàn bộ thay đổi hợp lệ. Sau đó chạy `git rev-parse HEAD` và điền SHA cuối vào mục 1 của report.
7. Chạy lại ngay trước khi nộp:

```powershell
python -m pytest -q
python scripts/validate_logs.py
python scripts/validate_dashboard.py
git status --short
git grep -n "sk-lf-"
```

Lệnh `git grep` cuối phải không in ra secret thật. Chuỗi minh họa trong tài liệu nếu có phải được kiểm tra thủ công.
