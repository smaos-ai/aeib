"""End-to-end integration tests for the full 5-stage pipeline."""

from pathlib import Path
from ocr_audit.pipeline_runner import HybridAuditPipeline


def test_pipeline_on_toxic_receipt_fixture():
    fixture_path = Path(__file__).parent / "fixtures" / "toxic_receipt_504.jsonl"
    pipeline = HybridAuditPipeline(fixture_path)
    res = pipeline.run()

    s = res["summary"]
    assert s["total_traces_ingested"] == 6
    assert s["stage1_noise_reduction_pct"] >= 80.0
    assert s["stage5_verified_findings"] == 1
    assert s["line_drift_pct"] == 0.00

    finding = res["findings"][0]
    assert finding["anchor_lines"]["start_line"] == 6
    assert finding["category"] == "UNJUSTIFIED_CONFIRMED_ON_WIRE_FAULT"

    patch = pipeline.generate_remediation_patch(res)
    assert "-  \"verdict\": \"CONFIRMED\"" in patch
    assert "+  \"verdict\": \"UNKNOWN\"" in patch
