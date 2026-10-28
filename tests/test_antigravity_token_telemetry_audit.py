"""
Verification suite for tools/antigravity_token_telemetry_audit.py.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.oct2026_runtime_trace_contextcart_and_hazard_gate import ContextRecordKind
from tools.antigravity_token_telemetry_audit import (
    analyze_transcript_jsonl,
    classify_transcript_step_kind,
    estimate_bpe_tokens_from_utf8_bytes,
    main,
)


def test_bpe_token_estimator_and_step_classification() -> None:
    assert estimate_bpe_tokens_from_utf8_bytes(0) == 0
    assert estimate_bpe_tokens_from_utf8_bytes(-5) == 0
    assert estimate_bpe_tokens_from_utf8_bytes(1) == 1
    assert estimate_bpe_tokens_from_utf8_bytes(4) == 1
    assert estimate_bpe_tokens_from_utf8_bytes(5) == 2

    assert (
        classify_transcript_step_kind({"source": "USER_EXPLICIT", "type": "OTHER", "content": "hi"})
        == ContextRecordKind.USER_INSTRUCTION
    )
    assert (
        classify_transcript_step_kind({"source": "OTHER", "type": "USER_INPUT", "content": "hi"})
        == ContextRecordKind.USER_INSTRUCTION
    )
    assert (
        classify_transcript_step_kind({"source": "SYSTEM", "type": "TOOL", "content": "EO1_APPROVAL id=1"})
        == ContextRecordKind.EO1_APPROVAL_RECORD
    )
    assert (
        classify_transcript_step_kind({"source": "SYSTEM", "type": "TOOL", "content": "OperationApprovalGrant id=1"})
        == ContextRecordKind.EO1_APPROVAL_RECORD
    )
    assert (
        classify_transcript_step_kind({"source": "SYSTEM", "type": "RULE", "content": "SAFETY_INVARIANT lock"})
        == ContextRecordKind.SAFETY_INVARIANT
    )
    assert (
        classify_transcript_step_kind({"source": "SYSTEM", "type": "RULE", "content": "STRICT EPISTEMIC lock"})
        == ContextRecordKind.SAFETY_INVARIANT
    )
    assert (
        classify_transcript_step_kind({"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "plan"})
        == ContextRecordKind.SCRATCH_SUMMARY
    )
    assert (
        classify_transcript_step_kind({"source": "MODEL", "type": "THOUGHT", "content": "note"})
        == ContextRecordKind.SCRATCH_SUMMARY
    )
    assert (
        classify_transcript_step_kind({"source": "SYSTEM", "type": "TOOL_OUTPUT", "content": "raw json"})
        == ContextRecordKind.TOOL_OBSERVATION
    )
    assert (
        classify_transcript_step_kind({"source": "SYSTEM", "type": "UNKNOWN_STEP", "content": "raw"})
        == ContextRecordKind.TOOL_OBSERVATION
    )


def test_analyze_transcript_jsonl_and_cli_execution(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Transcript file not found"):
        analyze_transcript_jsonl(tmp_path / "nonexistent.jsonl")
    with pytest.raises(FileNotFoundError, match="Transcript file not found"):
        analyze_transcript_jsonl(tmp_path)

    transcript_file = tmp_path / "sample_transcript.jsonl"
    line_dl = "Downloading nvidia-cusparselt-cu12 (150.1MiB)"
    line_bar = " ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 150.1/150.1 MiB 18.2 MiB/s"
    bulky_tool_output = (
        line_dl
        + "\n"
        + line_bar
        + "\n"
        + ("RAW_JSON_OBSERVATION_LINE: " + ("X" * 80) + "\n") * 25
    )
    step1_content = "Verify APOE and ABL1 P00520 boundaries."
    step2_content = "OperationApprovalGrant appr-001 must never be compressed."
    step4_content = "Completed verification."
    step4_thinking = "Checked P00520 rigid core 75-512."
    step4_tool_calls = [{"z_arg": 2, "a_arg": 1}]
    step4_combined = "\n".join(
        [step4_content, step4_thinking, json.dumps(step4_tool_calls, sort_keys=True)]
    )
    step5_content = "Short tool observation below archival threshold."
    step6_content = "Second planner turn without token counters."

    steps = [
        {
            "step_index": 1,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": step1_content,
        },
        {
            "step_index": 2,
            "source": "SYSTEM",
            "type": "TOOL_OUTPUT",
            "content": step2_content,
        },
        {
            "step_index": 3,
            "source": "SYSTEM",
            "type": "TOOL_OUTPUT",
            "content": bulky_tool_output,
        },
        {
            "step_index": 4,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "content": step4_content,
            "thinking": step4_thinking,
            "tool_calls": step4_tool_calls,
            "input_tokens": 1200,
            "cache_read_tokens": 8800,
            "output_tokens": 350,
        },
        {
            "step_index": 5,
            "source": "SYSTEM",
            "type": "TOOL_OUTPUT",
            "content": step5_content,
        },
        {
            "step_index": 6,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "content": step6_content,
        },
    ]
    transcript_file.write_text(
        "\n".join(json.dumps(s) for s in steps) + "\n",
        encoding="utf-8",
    )

    report_out = tmp_path / "telemetry_report.json"
    rc = main(
        [
            "--transcript",
            str(transcript_file),
            "--threshold-bytes",
            "512",
            "--json-out",
            str(report_out),
        ]
    )
    assert rc == 0
    raw_report_text = report_out.read_text(encoding="utf-8")
    assert '\n  "archived_observation_count": 1,' in raw_report_text
    assert raw_report_text.index('"archived_observation_count"') < raw_report_text.index(
        '"transcript_path"'
    )

    saved = json.loads(raw_report_text)
    expected_s1_bytes = len(step1_content.encode("utf-8"))
    expected_s2_bytes = len(step2_content.encode("utf-8"))
    expected_s3_bytes = len(bulky_tool_output.encode("utf-8"))
    expected_s4_bytes = len(step4_combined.encode("utf-8"))
    expected_s5_bytes = len(step5_content.encode("utf-8"))
    expected_s6_bytes = len(step6_content.encode("utf-8"))
    expected_raw_total = (
        expected_s1_bytes
        + expected_s2_bytes
        + expected_s3_bytes
        + expected_s4_bytes
        + expected_s5_bytes
        + expected_s6_bytes
    )
    expected_bloat_bytes = len(line_dl.encode("utf-8")) + len(line_bar.encode("utf-8"))
    expected_sha256 = hashlib.sha256(
        b"".join(
            p.encode("utf-8")
            for p in (
                step1_content,
                step2_content,
                bulky_tool_output,
                step4_combined,
                step5_content,
                step6_content,
            )
        )
    ).hexdigest()

    assert saved["total_steps"] == 6
    assert saved["planner_turn_count"] == 2
    assert saved["transcript_payload_sha256"] == expected_sha256
    assert saved["host_input_tokens_sum"] == 1200
    assert saved["host_cache_read_tokens_sum"] == 8800
    assert saved["host_output_tokens_sum"] == 350
    assert saved["host_total_prompt_tokens"] == 10000
    assert saved["raw_total_bytes"] == expected_raw_total
    assert saved["archived_observation_count"] == 1
    assert saved["lossless_sha256_recoveries_verified"] == 1
    assert saved["reclaimed_bytes"] == expected_raw_total - saved["post_contextcart_bytes"]
    assert saved["reclaimed_bytes"] > 2000
    assert (
        saved["reclaimed_estimated_tokens"]
        == saved["raw_estimated_tokens"] - saved["post_contextcart_estimated_tokens"]
    )
    assert saved["cli_progress_bar_bloat_bytes"] == expected_bloat_bytes
    assert saved["bytes_by_kind"] == {
        "USER_INSTRUCTION": expected_s1_bytes,
        "SAFETY_INVARIANT": 0,
        "EO1_APPROVAL_RECORD": expected_s2_bytes,
        "TOOL_OBSERVATION": expected_s3_bytes + expected_s5_bytes,
        "SCRATCH_SUMMARY": expected_s4_bytes + expected_s6_bytes,
    }
