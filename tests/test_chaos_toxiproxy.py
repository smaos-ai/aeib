"""Pytest suite for AEIB Toxiproxy Chaos Harness."""
import pytest
from benchmarks.chaos_toxiproxy import run_chaos_experiment

def test_toxiproxy_tcp_rst_zero_duplicates():
    res = run_chaos_experiment("tcp_rst", num_episodes=20)
    assert res["trapped_faults"] == 20
    assert res["duplicate_mutations"] == 0
    assert res["status"] == "PASS_ZERO_DUPLICATES"

def test_toxiproxy_half_open_zero_duplicates():
    res = run_chaos_experiment("half_open", num_episodes=20)
    assert res["trapped_faults"] == 20
    assert res["duplicate_mutations"] == 0
    assert res["status"] == "PASS_ZERO_DUPLICATES"

def test_toxiproxy_latency_jitter_zero_duplicates():
    res = run_chaos_experiment("latency_jitter", num_episodes=20)
    assert res["duplicate_mutations"] == 0
    assert res["status"] == "PASS_ZERO_DUPLICATES"
