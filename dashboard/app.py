"""Dashboard 6 panel cho Day 13, đọc data/logs.jsonl.

Panel không hard-code: tiêu đề, đơn vị, phép tổng hợp và threshold đều lấy từ
config/dashboard.yaml, nên dashboard chạy được và validator báo hợp lệ là cùng
nói về một contract. Sửa contract thì dashboard đổi theo, không lệch âm thầm.

Chạy:  streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Dùng lại đúng hàm percentile của API để dashboard và /metrics không lệch nhau.
from app.metrics import percentile

CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"

OPERATOR_LABEL = {"lte": "≤", "gte": "≥"}


def load_contract() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]


# Đọc ở module scope vì @st.fragment(run_every=...) chốt chu kỳ lúc decorate,
# không nhận được giá trị truyền vào lúc gọi. Để refresh khớp contract thay vì
# hard-code, contract phải có mặt trước khi decorator chạy.
CONTRACT = load_contract()


def load_logs() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # Log hỏng một dòng không được làm sập cả dashboard.
            continue
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["ts"] = pd.to_datetime(frame["ts"], format="ISO8601", utc=True)
    frame["minute"] = frame["ts"].dt.floor("min")
    return frame


def within_window(frame: pd.DataFrame, minutes: int, ignore_window: bool) -> pd.DataFrame:
    if frame.empty or ignore_window:
        return frame
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return frame[frame["ts"] >= cutoff]


def passes(value: float, threshold: dict) -> bool:
    if threshold["operator"] == "lte":
        return value <= threshold["value"]
    return value >= threshold["value"]


def panel_header(panel: dict, value: float, display: str) -> None:
    threshold = panel["threshold"]
    ok = passes(value, threshold)
    operator = OPERATOR_LABEL[threshold["operator"]]
    st.markdown(f"#### {panel['title']}")
    left, right = st.columns([2, 3])
    # Label là phép tổng hợp mà threshold áp lên, kèm đơn vị từ contract — đọc
    # ảnh evidence là biết ngay con số này đang được so với cái gì.
    left.metric(f"{threshold['aggregation']} ({panel['unit']})", display)
    right.markdown(
        f"{'🟢 ĐẠT' if ok else '🔴 VƯỢT NGƯỠNG'} &nbsp;·&nbsp; "
        f"`{threshold['aggregation']} {operator} {threshold['value']}`",
        unsafe_allow_html=True,
    )


def rule_at(value: float) -> alt.Chart:
    """Đường threshold/SLO — bắt buộc phải nhìn thấy trên ảnh evidence."""
    return (
        alt.Chart(pd.DataFrame({"y": [value]}))
        .mark_rule(strokeDash=[6, 4], color="#c0392b")
        .encode(y="y:Q")
    )


def timeseries(frame: pd.DataFrame, y: str, unit: str, threshold_value: float | None) -> None:
    if frame.empty:
        st.caption("Chưa có dữ liệu trong cửa sổ thời gian này.")
        return
    chart = (
        alt.Chart(frame)
        .mark_line(point=True)
        .encode(
            x=alt.X("minute:T", title="Thời gian"),
            y=alt.Y(f"{y}:Q", title=unit),
            tooltip=["minute:T", f"{y}:Q"],
        )
    )
    if threshold_value is not None:
        chart = chart + rule_at(threshold_value)
    st.altair_chart(chart.properties(height=200), width='stretch')


# ---------------------------------------------------------------- panels

def render_latency(panel: dict, responses: pd.DataFrame) -> None:
    values = responses["latency_ms"].dropna().astype(int).tolist() if not responses.empty else []
    p50, p95, p99 = (percentile(values, p) for p in (50, 95, 99))
    panel_header(panel, p95, f"{p95:.0f}")
    a, b, c = st.columns(3)
    a.metric("p50", f"{p50:.0f} ms")
    b.metric("p95", f"{p95:.0f} ms")
    c.metric("p99", f"{p99:.0f} ms")
    if not responses.empty:
        series = responses.groupby("minute")["latency_ms"].quantile(0.95).reset_index()
        timeseries(series, "latency_ms", "ms (p95 mỗi phút)", panel["threshold"]["value"])


def render_traffic(panel: dict, requests: pd.DataFrame, minutes: int) -> None:
    count = len(requests)
    rate = count / minutes if minutes else 0.0
    panel_header(panel, rate, f"{rate:.2f}")
    st.caption(f"Tổng {count} request trong cửa sổ {minutes} phút.")
    if not requests.empty:
        series = requests.groupby("minute").size().reset_index(name="requests")
        timeseries(series, "requests", "request/phút", panel["threshold"]["value"])


def render_errors(panel: dict, requests: pd.DataFrame, failures: pd.DataFrame) -> None:
    rate = (len(failures) / len(requests) * 100) if len(requests) else 0.0
    panel_header(panel, rate, f"{rate:.2f}")
    if failures.empty:
        st.caption("Không có request_failed trong cửa sổ này.")
        return
    breakdown = failures["error_type"].value_counts().reset_index()
    breakdown.columns = ["error_type", "count"]
    st.bar_chart(breakdown.set_index("error_type"), height=200)


def render_cost(panel: dict, responses: pd.DataFrame) -> None:
    total = float(responses["cost_usd"].sum()) if not responses.empty else 0.0
    panel_header(panel, total, f"{total:.4f}")
    if not responses.empty:
        series = responses.groupby("minute")["cost_usd"].sum().reset_index()
        timeseries(series, "cost_usd", "USD/phút", None)


def render_tokens(panel: dict, responses: pd.DataFrame) -> None:
    tokens_in = int(responses["tokens_in"].sum()) if not responses.empty else 0
    tokens_out = int(responses["tokens_out"].sum()) if not responses.empty else 0
    # threshold sum_by_field áp cho từng field, nên lấy field lớn hơn để đánh giá.
    panel_header(panel, max(tokens_in, tokens_out), f"{tokens_in + tokens_out:,}")
    a, b = st.columns(2)
    a.metric("tokens_in", f"{tokens_in:,}")
    b.metric("tokens_out", f"{tokens_out:,}")
    if not responses.empty:
        series = (
            responses.groupby("minute")[["tokens_in", "tokens_out"]]
            .sum()
            .reset_index()
            .melt("minute", var_name="field", value_name="tokens")
        )
        chart = (
            alt.Chart(series)
            .mark_bar()
            .encode(
                x=alt.X("minute:T", title="Thời gian"),
                y=alt.Y("tokens:Q", title="tokens"),
                color=alt.Color("field:N", title=""),
                tooltip=["minute:T", "field:N", "tokens:Q"],
            )
        )
        st.altair_chart(chart.properties(height=200), width='stretch')


def render_quality(panel: dict, responses: pd.DataFrame) -> None:
    mean = float(responses["quality_score"].mean()) if not responses.empty else 0.0
    panel_header(panel, mean, f"{mean:.3f}")
    if not responses.empty:
        series = responses.groupby("minute")["quality_score"].mean().reset_index()
        timeseries(series, "quality_score", "score 0–1", panel["threshold"]["value"])


# ---------------------------------------------------------------- app

def main() -> None:
    st.set_page_config(page_title="Day 13 AI Observability", layout="wide")
    contract = CONTRACT
    minutes = contract["time_range_minutes"]
    refresh = contract["refresh_seconds"]

    st.title(contract["title"])
    st.caption(
        f"Nguồn: `data/logs.jsonl` · Time range {minutes} phút · "
        f"Refresh {refresh}s · Contract `config/dashboard.yaml` v{contract['schema_version']}"
    )

    with st.sidebar:
        st.header("Contract")
        st.caption("Chỉ đọc — sửa ở config/dashboard.yaml")
        st.code(
            f"time_range_minutes: {minutes}\nrefresh_seconds: {refresh}\npanels: {len(contract['panels'])}",
            language="yaml",
        )
        ignore_window = st.checkbox(
            "Bỏ qua time range (debug)",
            value=False,
            help="Chỉ dùng khi log cũ hơn cửa sổ. Ảnh evidence phải chụp lúc TẮT.",
        )
        if ignore_window:
            st.warning("Đang xem toàn bộ log — không dùng ảnh này làm evidence.")

    render_dashboard(contract, minutes, ignore_window, refresh)


@st.fragment(run_every=CONTRACT["refresh_seconds"])
def render_dashboard(contract: dict, minutes: int, ignore_window: bool, refresh: int) -> None:
    frame = within_window(load_logs(), minutes, ignore_window)
    if frame.empty:
        st.warning(
            "Chưa có log trong cửa sổ. Chạy API rồi `python scripts/load_test.py`, "
            "hoặc bật 'Bỏ qua time range' ở sidebar để xem log cũ."
        )
        return

    requests = frame[frame["event"] == "request_received"]
    responses = frame[frame["event"] == "response_sent"]
    failures = frame[frame["event"] == "request_failed"]

    renderers = {
        "latency": lambda p: render_latency(p, responses),
        "traffic": lambda p: render_traffic(p, requests, minutes),
        "errors": lambda p: render_errors(p, requests, failures),
        "cost": lambda p: render_cost(p, responses),
        "tokens": lambda p: render_tokens(p, responses),
        "quality": lambda p: render_quality(p, responses),
    }

    panels = contract["panels"]
    for row_start in range(0, len(panels), 2):
        for column, panel in zip(st.columns(2), panels[row_start : row_start + 2]):
            with column, st.container(border=True):
                renderers[panel["id"]](panel)

    st.caption(f"Cập nhật lúc {datetime.now(timezone.utc):%H:%M:%S} UTC · tự làm mới mỗi {refresh}s")


main()
