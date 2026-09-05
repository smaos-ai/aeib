# Phase 78 GitNexus Pre-Merge Gate Definitions

## Purpose
Pre-merge gating for smart contract PRs. All incoming changes to contract bytecode, ABI, and state management must pass these checks before merge.

## Gate Definitions

### GATE: SELFDESTRUCT_BLOCK (CRITICAL)
**Risk Level:** CRITICAL
**Detection:** Opcode FF detected in contract bytecode
**Action:** BLOCK merge immediately
**Rationale:** SELFDESTRUCT allows contract self-destruction, breaking state guarantees

```
Detection Pattern: bytecode contains "ff" or "fF"
```

### GATE: DELEGATECALL_DETECTION (HIGH)
**Risk Level:** HIGH
**Detection:** Opcode F4 detected in contract bytecode
**Action:** REQUIRE manual review and approval from Team 5 lead
**Rationale:** DELEGATECALL can delegate execution to untrusted contracts

```
Detection Pattern: bytecode contains "f4" or "F4"
```

### GATE: STORAGE_COLLISION_DETECT (HIGH)
**Risk Level:** HIGH
**Detection:** Same storage slot used by multiple functions/contracts
**Action:** BLOCK merge, require refactoring
**Rationale:** Storage collisions cause state corruption and reentrancy vulnerabilities

```
Detection Pattern:
  - contract_state_slots table: UNIQUE(contract_address, slot_key) violation
  - Multiple writes to same slot_key in same contract within same execution_id
```

### GATE: IMPACT_THRESHOLD (HIGH)
**Risk Level:** HIGH if impact > 70%
**Detection:** gitnexus_detect_changes() returns >70% codebase impact
**Action:** BLOCK merge, require architecture review
**Rationale:** Large changes risk cascading failures across consensus layers

```
Threshold: > 70% of symbols affected
Calculation: (affected_symbols / total_symbols) * 100
```

### GATE: EXECUTION_FLOW_VALIDATION (MEDIUM)
**Risk Level:** MEDIUM
**Detection:** New execution flows added to contract_executions path
**Action:** REQUIRE unit tests for all new flows
**Rationale:** Untested flows can cause state inconsistency during settlement

```
Affected Processes:
  - contract_deployment (evm_executor::deploy_contract)
  - contract_execution (evm_executor::execute_contract_function)
  - state_commitment (contract_state_store::store_contract_state)
  - settlement (contract_state_store::settle_contract_execution)
```

## Pre-Merge Workflow

1. **Analyze PR Changes** (gitnexus_detect_changes)
   - Identify all modified symbols
   - Report execution flows affected

2. **Run Impact Analysis** (gitnexus_impact for each symbol)
   - Check blast radius (upstream callers)
   - Flag if impact >= HIGH

3. **Check Critical Gates**
   - SELFDESTRUCT_BLOCK: BLOCK if triggered
   - DELEGATECALL_DETECTION: REQUIRE review if triggered
   - STORAGE_COLLISION_DETECT: BLOCK if violated

4. **Calculate Impact Score**
   - If impact > 70%: BLOCK, require architecture review
   - If impact 40-70%: WARN, require unit tests
   - If impact < 40%: PROCEED

5. **Approval Required**
   - CRITICAL gates: Team 5 lead + Opus reviewer
   - HIGH gates: Team 5 lead
   - MEDIUM gates: Any Team 5 member

## Implementation Notes

- All checks run in `cargo test --test phase_78_smart_contracts`
- GitNexus analysis integrated into CI/CD pipeline
- Results logged to contract_settlements table (audit trail)
- Failed PRs cannot be merged until all gates pass
