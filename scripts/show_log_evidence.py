"""In một khung gọn từ data/logs.jsonl để chụp làm evidence CP1.

Mỗi bản ghi in ra đều có đồng thời correlation ID, đủ 5 field metadata và một
chuỗi [REDACTED_*] — đúng hai thứ CP1 yêu cầu chứng minh, trong cùng một ảnh.

Chạy: python scripts/show_log_evidence.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
METADATA_FIELDS = ("user_id_hash", "session_id", "feature", "model", "env")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="In log evidence cho CP1")
    parser.add_argument("--limit", type=int, default=3, help="Số bản ghi in ra")
    args = parser.parse_args()

    if not LOG_PATH.exists():
        print("Chưa có data/logs.jsonl — chạy API rồi python scripts/load_test.py trước.")
        return 1

    records = [json.loads(line) for line in LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Chỉ lấy bản ghi chứng minh được CẢ HAI yêu cầu cùng lúc.
    matches = [
        r for r in records
        if r.get("correlation_id") and "REDACTED" in json.dumps(r, ensure_ascii=False)
    ]

    if not matches:
        print("Không tìm thấy bản ghi nào có cả correlation ID và [REDACTED_*].")
        print("Chạy python scripts/load_test.py để sinh log từ data/sample_queries.jsonl.")
        return 1

    print("=== LOG EVIDENCE: CORRELATION ID + PII ĐÃ REDACT ===")
    for record in matches[: args.limit]:
        payload = record.get("payload", {})
        message = payload.get("message_preview") or payload.get("answer_preview") or ""
        print()
        print(f"  correlation_id : {record['correlation_id']}")
        print(f"  event          : {record['event']}")
        for field in METADATA_FIELDS:
            print(f"  {field:<15}: {record.get(field)}")
        print(f"  message        : {message}")

    print()
    print(f"Tổng {len(matches)} bản ghi thoả cả hai điều kiện trong {LOG_PATH.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
