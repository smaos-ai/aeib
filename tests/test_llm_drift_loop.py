"""Pytest suite for AEIB LLM Prompt Drift Loop Benchmark."""
import pytest
from benchmarks.llm_drift_loop import run_prompt_drift_benchmark

def test_prompt_drift_invariants():
    res = run_prompt_drift_benchmark(episodes=25, seed=42)
    assert res["naive_duplicates"] == 25
    assert res["payload_hash_duplicates"] > 0
    assert res["aeib_duplicates"] == 0
    assert res["status"] == "PASS_ZERO_DUPLICATES"
