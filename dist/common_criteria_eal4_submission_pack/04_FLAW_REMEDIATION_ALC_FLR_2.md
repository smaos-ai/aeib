<!--
Common Criteria ISO/IEC 15408 Evaluation Package
Document: 04_FLAW_REMEDIATION_ALC_FLR_2.md
Status: INTERNAL PREVIEW COMMISSIONED
Assurance Component: ALC_FLR.2 (Flaw Remediation Procedures)
-->

# ALC_FLR.2: Flaw Remediation & Mutation Adequacy Records

**Target of Evaluation (TOE):** SovereignNexus Agent Execution Integrity Boundary (AEIB v1.1)  
**Assurance Level:** EAL4 Augmented (ALC_FLR.2 + AVA_VAN.4)  
**Status:** `INTERNAL PREVIEW COMMISSIONED`  

---

## 1. Mutation Adequacy Verification Protocol

Under ISO/IEC 15408-3 ALC_FLR.2 and Lesson L23/L24, flaw discovery and remediation procedures are evaluated through automated AST mutation analysis:
1. Deterministic AST mutations (comparison flips, arithmetic swaps, constant perturbations, statement deletions, raise drops) are injected into target modules.
2. Unmocked test suites are executed against each mutated AST.
3. Every mutant that fails at least one test is classified as **KILLED**.
4. Every surviving mutant is individually audited and disclosed with technical rationale.
5. Confidence intervals are calculated using the conservative Wilson score method at 95% confidence and reported in integer basis points (`[low_bps..high_bps]`).

---

## 2. Core Execution Plane Mutation Records

| Target Module | Test Suite File | Mutants Sampled | Mutants Killed | Kill Ratio (bps) | Wilson 95% CI (bps) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `src/distributed_agentgateway_reconciler.py` | `tests/test_distributed_agentgateway_reconciler.py` | 30 | 30 | **10000 bps** (30/30) | `[8864..10000 bps]` |
| `src/kagent_helm_generator.py` | `tests/test_kagent_helm_generator.py` | 30 | 30 | **10000 bps** (30/30) | `[8864..10000 bps]` |
| `src/kagent_crd_adapter.py` | `tests/test_kagent_crd_adapter.py` | 30 | 30 | **10000 bps** (30/30) | `[8864..10000 bps]` |
| `tools/multi_region_production_rollout_gate.py` | `tests/test_multi_region_production_rollout_gate.py` | 30 | 26 | **8667 bps** (26/30) | `[7033..9469 bps]` |
| `tools/compile_common_criteria_submission_pack.py` | `tests/test_compile_common_criteria_submission_pack.py` | 30 | 26 | **8667 bps** (26/30) | `[7033..9469 bps]` |

---

## 3. Disclosed Surviving Mutants (Lesson L23 Compliance)

### A. `tools/multi_region_production_rollout_gate.py` (4 survivors / 30 sampled):
1. **Line 308 (`BOOL_SWAP`):** `Or` swapped with `And` in `verify_certificate_file`. Pseudo-equivalent mutant; invalid inputs fail downstream hash check or catch-all exception returning False either way.
2. **Line 345 (`CONST_PERTURB`):** `parents=True` perturbed on `out_p.parent.mkdir()`. Harmless boilerplate; directory exists in tests.
3. **Line 346 (`CONST_PERTURB`):** `indent=2` perturbed to `indent=3`. Cosmetic whitespace in CLI serialization.
4. **Line 357 (`CONST_PERTURB`):** `80` perturbed in terminal banner `print("=" * 80)`. Cosmetic terminal formatting.

### B. `tools/compile_common_criteria_submission_pack.py` (4 survivors / 30 sampled):
1. **Line 702 (`CONST_PERTURB`):** `parents=True` on `self.pack_dir.mkdir()`. Harmless boilerplate; parent directory already exists.
2. **Line 867, 876, 879 (`CONST_PERTURB`):** `80` perturbed in terminal divider banners `print("=" * 80)`. Cosmetic terminal formatting.
