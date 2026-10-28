#!/usr/bin/env python3
"""
Falsification Suite for SemanticScionCompilerEngine (`src/semantic_scion_compiler.py`).
"""

import pytest

from src.semantic_scion_compiler import SemanticScionCompilerEngine, sha256_jcs_caid


def test_semantic_scion_compiler_produces_6_vectors_and_receipt() -> None:
    prompt = (
        "Bit fundament go make long life based on truth... "
        "constant time everyday ground build marathon 2+2=4"
    )
    report = SemanticScionCompilerEngine.for_compile_query(
        raw_brainstorm_prompt=prompt,
        target_file_path="src/lajolla_covering_verifier.py",
        rule_tier=1,
        noise_comments_count=14,
    )
    assert len(report.decomposed_vectors) == 6
    assert report.resolved_rule_tier == 1
    assert report.resolved_rule_id == "rule_tier_1_automatic"
    assert report.filter_noise_dropped == 14
    assert report.raw_query_caid.startswith("sha256:")
    assert report.execution_receipt_caid.startswith("sha256:")

    # Deterministic across compile_query and for_compile_query
    report_2 = SemanticScionCompilerEngine.compile_query(
        raw_brainstorm_prompt=prompt,
        target_file_path="src/lajolla_covering_verifier.py",
        rule_tier=1,
        noise_comments_count=14,
    )
    assert report_2 == report

    # Changing target_file_path or tier changes receipt_caid
    report_tier4 = SemanticScionCompilerEngine.compile_query(
        raw_brainstorm_prompt=prompt,
        target_file_path="src/lajolla_covering_verifier.py",
        rule_tier=4,
        noise_comments_count=0,
    )
    assert report_tier4.resolved_rule_id == "rule_tier_4_escalate_to_human"
    assert report_tier4.execution_receipt_caid != report.execution_receipt_caid

    # Verify defaults when rule_tier and noise_comments_count are omitted
    report_defaults = SemanticScionCompilerEngine.compile_query(
        raw_brainstorm_prompt=prompt,
        target_file_path="src/lajolla_covering_verifier.py",
    )
    assert report_defaults.resolved_rule_tier == 1
    assert report_defaults.resolved_rule_id == "rule_tier_1_automatic"
    assert report_defaults.filter_noise_dropped == 0
    with pytest.raises(Exception):
        report_defaults.resolved_rule_tier = 2  # type: ignore[misc]


def test_empty_prompt_or_invalid_tier_halts() -> None:
    with pytest.raises(ValueError, match="ERR_EMPTY_BRAINSTORM_PROMPT"):
        SemanticScionCompilerEngine.for_compile_query("   ", "src/main.py")

    with pytest.raises(ValueError, match="ERR_EMPTY_TARGET_FILE_PATH"):
        SemanticScionCompilerEngine.for_compile_query("valid prompt", "   ")

    with pytest.raises(ValueError, match="ERR_INVALID_RULE_TIER_1_TO_4"):
        SemanticScionCompilerEngine.for_compile_query("valid prompt", "src/main.py", rule_tier=5)

    with pytest.raises(ValueError, match="ERR_INVALID_RULE_TIER_1_TO_4"):
        SemanticScionCompilerEngine.for_compile_query("valid prompt", "src/main.py", rule_tier=0)

    with pytest.raises(ValueError, match="ERR_INVALID_RULE_TIER_1_TO_4"):
        SemanticScionCompilerEngine.for_compile_query("valid prompt", "src/main.py", rule_tier=True)

    with pytest.raises(ValueError, match="ERR_NEGATIVE_NOISE_COMMENTS_COUNT"):
        SemanticScionCompilerEngine.for_compile_query(
            "valid prompt", "src/main.py", rule_tier=1, noise_comments_count=-1
        )

    with pytest.raises(ValueError, match="ERR_NEGATIVE_NOISE_COMMENTS_COUNT"):
        SemanticScionCompilerEngine.for_compile_query(
            "valid prompt", "src/main.py", rule_tier=1, noise_comments_count=True
        )

    with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_IN_JCS"):
        sha256_jcs_caid({"bad": 1.25})

    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        sha256_jcs_caid({42: "val"})

    assert sha256_jcs_caid(b"raw_bytes").startswith("sha256:")
