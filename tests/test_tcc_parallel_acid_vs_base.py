# File: tests/test_tcc_parallel_acid_vs_base.py
"""
Verification suite for SQLite ACID Try-Confirm-Cancel (TCC) vs. BASE Duplicate-Mutation Prevention.
"""
from pathlib import Path
from tests.test_tcc_parallel_acid_vs_base_anomalies import (
    test_arxiv_2609_15397_parallel_budget_anomaly_and_2609_29095_late_commit,
    test_concurrent_multi_threaded_tcc_reservation_stress,
    test_occ_cas_context_manifest_drift_prevention_at31_at50,
    test_occ_cas_versioning_and_policy_epoch_drift_prevention,
    test_structured_task_scope_jep480_shutdown_on_failure_and_tcc_rollback,
    test_structured_task_scope_spec_caid_dto_contract_violation_triggers_shutdown,
)


def test_sqlite_tcc_parallel_acid_vs_base_proof(tmp_path: Path) -> None:
    test_arxiv_2609_15397_parallel_budget_anomaly_and_2609_29095_late_commit(tmp_path)
    test_concurrent_multi_threaded_tcc_reservation_stress(tmp_path)
    test_structured_task_scope_jep480_shutdown_on_failure_and_tcc_rollback(tmp_path)
    test_structured_task_scope_spec_caid_dto_contract_violation_triggers_shutdown(tmp_path)
    test_occ_cas_versioning_and_policy_epoch_drift_prevention(tmp_path)
    test_occ_cas_context_manifest_drift_prevention_at31_at50(tmp_path)
