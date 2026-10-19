#!/usr/bin/env python3
"""
tests/test_live_telemetry_widget.py
================================================================================
Test suite for the AEIB Live Telemetry & Auditor Cockpit Widget (Pillar 5).
Evaluates metric aggregation across the 4 concurrent worker domains and HTML rendering.
"""

from pathlib import Path
import json
import pytest

from src.ciso_dashboard.live_telemetry_widget import LiveTelemetryAggregator


def test_live_telemetry_aggregator_metrics(tmp_path: Path):
    stream_file = tmp_path / "test_stream.jsonl"
    events = [
        {
            "timestamp": "2026-10-19T01:00:00Z",
            "worker_id": "WORKER-1-FIN",
            "stage": "STATE_LATCH",
            "status": "EFFECT_INDETERMINATE",
            "data": {"retry_safe": False, "observed_duplicates": 0},
        },
        {
            "timestamp": "2026-10-19T01:00:01Z",
            "worker_id": "WORKER-3-IAPS",
            "stage": "QUARANTINE",
            "status": "SESSION_ISOLATED",
            "data": {"is_quarantined": True},
        },
        {
            "timestamp": "2026-10-19T01:00:02Z",
            "worker_id": "WORKER-4-SCITT",
            "stage": "TRANSPARENCY",
            "status": "MERKLE_ANCHORED",
            "data": {"inclusion_proof_valid": True},
        },
    ]

    with open(stream_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    aggregator = LiveTelemetryAggregator(stream_file)
    stats = aggregator.load_and_aggregate()

    assert stats["events_count"] == 3
    assert stats["observed_duplicates"] == 0
    assert stats["blocked_retries"] == 1
    assert stats["quarantined_sessions"] == 1
    assert stats["scitt_receipts_verified"] == 1

    # Render HTML
    html_out = tmp_path / "dashboard.html"
    aggregator.generate_html_cockpit(html_out)
    assert html_out.exists()
    html_content = html_out.read_text(encoding="utf-8")
    assert "AEIB Real-Time Auditor Cockpit" in html_content
    assert "WORKER-1-FIN" in html_content
    assert "WORKER-3-IAPS" in html_content
    assert "WORKER-4-SCITT" in html_content
