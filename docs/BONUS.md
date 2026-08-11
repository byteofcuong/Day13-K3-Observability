# Bonus — Cost Optimization và Audit Log

## Cost Optimization

Giải pháp giới hạn output token được bật/tắt runtime. Mặc định giải pháp tắt để
giữ nguyên baseline; khi bật, `MAX_OUTPUT_TOKENS` mặc định là 160.

Chạy API rồi tạo phép đo before/after trên cùng 10 request khi `cost_spike` bật:

```powershell
uvicorn app.main:app --env-file .env
python scripts/run_bonus_evidence.py
```

Script lưu số liệu tại `submission/evidence/bonus-cost-before-after.json`. Chụp
output hoặc dashboard và lưu ảnh trong `submission/evidence/` theo rubric.

## Audit Log

Các sự kiện `incident.enable`, `incident.disable` và `config.change` được append
vào file riêng do `AUDIT_LOG_PATH` cấu hình (mặc định `data/audit.jsonl`). Mỗi
record có timestamp UTC, actor, correlation ID, môi trường và trạng thái
before/after. Chuỗi trong trạng thái được PII scrub trước khi ghi.

```powershell
Get-Content data/audit.jsonl | ConvertFrom-Json | Format-Table ts,action,target,correlation_id
python -m pytest tests/test_bonus.py -q
```
