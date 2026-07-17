# APAC 6-Agent Parallel Dispatch
**Date:** 2026-06-06  
**Deadline:** Aug 1, 2026  
**Status:** Ready for dispatch  

---

## Dispatch Summary

6 independent agents working in parallel on isolated file domains. **Zero file overlap** — each agent owns complete subsystem.

| Agent | Task | Files Owned | Tests | Deadline |
|-------|------|-------------|-------|----------|
| Agent 1 | Project Setup & Scaffolding | `crates/siss-apac-expansion/Cargo.toml`, `src/lib.rs` | Setup verification | Jun 7 |
| Agent 2 | Regional Compliance Framework | `src/compliance/**` | 8 compliance tests | Jun 12 |
| Agent 3 | Multi-Currency Settlement | `src/settlement/**` | 10 settlement tests | Jun 19 |
| Agent 4 | SDK Localization Framework | `src/localization/**` | 12 localization tests | Jun 26 |
| Agent 5 | Market Intelligence & TAM | `src/market_intelligence/**` | 12 market tests | Jul 3 |
| Agent 6 | Operational Playbook Generator | `src/playbook/**` | 8 playbook tests + 1 integration | Jul 10 |

---

## Agent 1: Project Setup & Scaffolding

**Owner:** Agent 1  
**Timeline:** Jun 6-7 (1 day)  
**Files:** 
- `crates/siss-apac-expansion/Cargo.toml` (create)
- `crates/siss-apac-expansion/src/lib.rs` (create)
- `crates/siss-apac-expansion/src/tests.rs` (create - empty)
- Root `Cargo.toml` (modify - add workspace member)

**Goal:** Scaffold crate with module structure, all dependencies declared, basic compilation passing.

**TDD Discipline:**
1. Create `Cargo.toml` with all future dependencies
2. Create `src/lib.rs` with module declarations (mod compliance, settlement, localization, market_intelligence, playbook)
3. Run `cargo check -p siss-apac-expansion` → must pass
4. Run `cargo test -p siss-apac-expansion --lib` → must compile (no tests yet)

**Success Criteria:**
- [x] Crate compiles cleanly (`cargo check -p siss-apac-expansion`)
- [x] All 5 modules declared in lib.rs
- [x] Workspace member added to root Cargo.toml
- [x] Clippy clean
- [x] Git commit: "feat: scaffold siss-apac-expansion crate"

**Output:** One commit, `cargo check` passes.

---

## Agent 2: Regional Compliance Framework

**Owner:** Agent 2  
**Timeline:** Jun 7-12 (5 days)  
**Files:** 
- `crates/siss-apac-expansion/src/compliance/mod.rs`
- `crates/siss-apac-expansion/src/compliance/rules.rs`
- `crates/siss-apac-expansion/src/compliance/validator.rs`
- `crates/siss-apac-expansion/migrations/001_compliance_registry.sql`
- `crates/siss-apac-expansion/src/tests.rs` (add compliance_tests module)

**Goal:** Complete compliance registry covering Singapore PDPA, Australia Privacy Act, Japan APPI, Korea PIPA, India DPDP.

**TDD Discipline:**
1. Write `compliance_tests` in `tests.rs` FIRST (all 8 tests failing)
2. Implement `rules.rs` (Country enum, ComplianceRequirement struct, get_country_requirements)
3. Implement `validator.rs` (ComplianceValidator with 4 validation methods)
4. Implement `mod.rs` (ComplianceRegistry with registry logic)
5. Run tests → all pass
6. Run `cargo clippy -p siss-apac-expansion` → clean
7. Git commit: "feat: regional compliance framework"

**Tests to Write (8 total):**
- test_regional_compliance_coverage
- test_singapore_pdpa_requirements
- test_australia_privacy_act
- test_japan_appi_requirements
- test_korea_pipa_requirements
- test_india_dpdp_requirements
- test_data_residency_validation
- test_full_compliance_validation
- test_compliance_validation_fails_on_residency

**Success Criteria:**
- [x] 8 tests passing
- [x] `cargo clippy` clean
- [x] No warnings
- [x] Migration file created (001_compliance_registry.sql)

**Output:** One commit with all compliance code + migration.

---

## Agent 3: Multi-Currency Settlement with Stripe Connect

**Owner:** Agent 3  
**Timeline:** Jun 12-19 (7 days)  
**Files:**
- `crates/siss-apac-expansion/src/settlement/mod.rs`
- `crates/siss-apac-expansion/src/settlement/stripe_integration.rs`
- `crates/siss-apac-expansion/src/settlement/payout_scheduler.rs`
- `crates/siss-apac-expansion/migrations/002_settlement_tracking.sql`
- `crates/siss-apac-expansion/src/tests.rs` (add settlement_tests module)

**Goal:** Stripe Connect integration for 8 APAC markets with local payout speeds (1-3 business days).

**TDD Discipline:**
1. Write `settlement_tests` in `tests.rs` FIRST (all 10 tests failing)
2. Implement `stripe_integration.rs` (Country enum with 8 markets, StripeAccount, SettlementTransaction, StripeSettlementManager)
3. Implement `payout_scheduler.rs` (PayoutScheduler with schedule/execute/complete/fail methods)
4. Implement `mod.rs` (re-exports)
5. Run tests → all pass
6. Migration file created (002_settlement_tracking.sql)

**Tests to Write (10 total):**
- test_multi_currency_settlement_valid
- test_stripe_account_creation
- test_payout_speed_singapore (1 day)
- test_payout_speed_australia (2 days)
- test_payout_speed_japan (3 days)
- test_settlement_transaction_creation
- test_payout_scheduler_workflow
- test_payout_cannot_execute_early
- And 2 more edge cases

**Success Criteria:**
- [x] 10 tests passing
- [x] 8 markets supported (SG, AU, JP, KR, IN, TH, VN, ID)
- [x] Payout speeds correct per region
- [x] `cargo clippy` clean

**Output:** One commit with settlement code + migration.

---

## Agent 4: Creator SDK Localization Framework

**Owner:** Agent 4  
**Timeline:** Jun 19-26 (7 days)  
**Files:**
- `crates/siss-apac-expansion/src/localization/mod.rs`
- `crates/siss-apac-expansion/src/localization/translator.rs`
- `crates/siss-apac-expansion/src/localization/onboarding_flows.rs`
- `crates/siss-apac-expansion/migrations/003_localization_strings.sql`
- `crates/siss-apac-expansion/src/tests.rs` (add localization_tests module)

**Goal:** 5-language SDK localization (Mandarin, Japanese, Korean, Hindi, Vietnamese) with region-specific onboarding flows.

**TDD Discipline:**
1. Write `localization_tests` in `tests.rs` FIRST (all 12 tests failing)
2. Implement `translator.rs` (Language enum, TranslationEntry, LocalizationTranslator, create_sdk_translations)
3. Implement `onboarding_flows.rs` (OnboardingFlow, OnboardingStep, RegionalOnboardingFlowGenerator)
4. Implement `mod.rs` (LocalizationFramework)
5. Run tests → all pass

**Tests to Write (12 total):**
- test_sdk_localization_complete
- test_mandarin_translations
- test_japanese_translations
- test_korean_translations
- test_hindi_translations
- test_vietnamese_translations
- test_singapore_onboarding_flow
- test_australia_onboarding_flow
- test_japan_onboarding_flow
- test_korea_onboarding_flow
- test_india_onboarding_flow
- test_localization_framework

**Success Criteria:**
- [x] 12 tests passing
- [x] 5 languages fully translated
- [x] 5 region-specific onboarding flows (SG, AU, JP, KR, IN)
- [x] Migration file created (003_localization_strings.sql)

**Output:** One commit with localization code + migration.

---

## Agent 5: Market Intelligence & TAM Calculator

**Owner:** Agent 5  
**Timeline:** Jun 26-Jul 3 (7 days)  
**Files:**
- `crates/siss-apac-expansion/src/market_intelligence/mod.rs`
- `crates/siss-apac-expansion/src/market_intelligence/tam_calculator.rs`
- `crates/siss-apac-expansion/src/market_intelligence/regional_data.rs`
- `crates/siss-apac-expansion/migrations/004_market_data.sql`
- `crates/siss-apac-expansion/src/tests.rs` (add market_intelligence_tests module)

**Goal:** TAM sizing (€480M total: SG €50M, AU €80M, JP €200M, KR €120M, IN €30M) with market penetration and growth projections.

**TDD Discipline:**
1. Write `market_intelligence_tests` in `tests.rs` FIRST (all 12 tests failing)
2. Implement `regional_data.rs` (RegionalMarketData struct, MarketMaturity, GoToMarketPhase, get_regional_data)
3. Implement `tam_calculator.rs` (TAMCalculator with total_tam, phase TAMs, penetration, revenue potential, growth projection)
4. Implement `mod.rs` (MarketIntelligence wrapper)
5. Run tests → all pass

**Tests to Write (12 total):**
- test_market_sizing_realistic (€480M total)
- test_phase_1_tam_july (€130M)
- test_phase_2_tam_august (€320M)
- test_phase_3_tam_september (€30M)
- test_singapore_market_data
- test_australia_market_data
- test_japan_market_data
- test_korea_market_data
- test_india_market_data
- test_penetration_calculation
- test_revenue_potential
- test_growth_projection

**Success Criteria:**
- [x] 12 tests passing
- [x] Total TAM = €480M verified
- [x] All 5 regions with realistic data
- [x] Migration file created (004_market_data.sql)

**Output:** One commit with market intelligence code + migration.

---

## Agent 6: Operational Playbook Generator

**Owner:** Agent 6  
**Timeline:** Jul 3-10 (7 days)  
**Files:**
- `crates/siss-apac-expansion/src/playbook/mod.rs`
- `crates/siss-apac-expansion/src/playbook/generator.rs`
- `crates/siss-apac-expansion/src/lib.rs` (modify - add playbook export)
- `crates/siss-apac-expansion/src/tests.rs` (add playbook_tests module)
- `crates/siss-apac-expansion/tests/integration_test.rs` (create)
- `crates/siss-apac-expansion/APAC_EXPANSION_SUMMARY.md` (create)

**Goal:** Synthesize all 5 components into unified operational playbook with 3 launch phases, success metrics, risk mitigation.

**TDD Discipline:**
1. Write `playbook_tests` in `tests.rs` FIRST (all 8 tests failing)
2. Implement `generator.rs` (OperationalPlaybook, OperationalPlaybookGenerator with generate method)
3. Implement `mod.rs` (re-exports)
4. Update `lib.rs` to export playbook module
5. Create integration test
6. Run tests → all pass + integration test passes
7. Run full suite: `cargo test -p siss-apac-expansion` → 50+ tests pass

**Tests to Write (8 total):**
- test_playbook_generation
- test_playbook_phase_1_coverage
- test_playbook_phase_2_coverage
- test_playbook_phase_3_coverage
- test_playbook_success_metrics
- test_playbook_risk_mitigation
- test_playbook_total_tam_coverage
- (integration_test covers full system)

**Success Criteria:**
- [x] 8 playbook tests passing
- [x] Integration test passing
- [x] Full suite: 50+ tests passing total
- [x] All clippy warnings resolved
- [x] Release build succeeds
- [x] Summary document created

**Output:** Two commits:
1. Playbook generator code + tests
2. Integration test + summary document

---

## Integration Checklist (After All Agents Complete)

Run AFTER all 6 agents finish:

```bash
# Full test suite
cargo test -p siss-apac-expansion

# Clippy
cargo clippy -p siss-apac-expansion --all-targets -- -D warnings

# Format check
cargo fmt -p siss-apac-expansion --check

# Release build
cargo build -p siss-apac-expansion --release

# Integration test
cargo test --test integration_test --release
```

**Expected Results:**
- ✅ 50+ tests passing
- ✅ 0 clippy warnings
- ✅ All code formatted
- ✅ Release build succeeds
- ✅ Integration test passes

---

## Parallel Execution Rules

### File Ownership (NO OVERLAP)
- Agent 1: `Cargo.toml`, `src/lib.rs`
- Agent 2: `src/compliance/**`, `migrations/001_*`, tests.rs (compliance_tests section)
- Agent 3: `src/settlement/**`, `migrations/002_*`, tests.rs (settlement_tests section)
- Agent 4: `src/localization/**`, `migrations/003_*`, tests.rs (localization_tests section)
- Agent 5: `src/market_intelligence/**`, `migrations/004_*`, tests.rs (market_intelligence_tests section)
- Agent 6: `src/playbook/**`, `src/lib.rs` (export only), tests.rs (playbook_tests section), integration_test.rs, summary doc

### Coordination Points
- Agent 1 completes FIRST (blocks Agent 2-6 until Cargo.toml ready)
- Agents 2-5 can work in parallel (no dependencies)
- Agent 6 starts after Agent 1 completes (needs lib.rs module structure)
- All agents share `src/tests.rs` but with separate test module sections (no conflicts)

### Conflict Resolution
If agents touch overlapping code:
- Agent with higher priority (lower number) commits first
- Agent with lower priority rebases and resolves conflicts
- Never force-push; use `git merge` for integration

---

## Success Metrics (Final Verification)

**By Aug 1, 2026:**
- ✅ 6 agents complete all tasks
- ✅ 50+ tests passing (8+10+12+12+8+1)
- ✅ 100% compliance coverage (5 countries)
- ✅ 8 settlement markets live (1-3 day payouts)
- ✅ 5 languages localized
- ✅ €480M TAM validated
- ✅ 3-phase operational playbook ready
- ✅ Zero critical bugs
- ✅ Zero security issues
- ✅ Release build ready for production

---

## Agent Communication Protocol

**Each agent should:**
1. Read this dispatch document
2. Read the detailed task in section matching your number
3. Execute TDD-first: write tests → implement → verify
4. Commit with explicit message
5. Return summary: what you built, test results, any blockers

**No agent should:**
- Touch files outside their section
- Modify other agents' code
- Block on other agents (work in parallel)
- Break existing tests

**Timeline:**
- Agent 1: Jun 6-7
- Agents 2-5: Jun 7-Jul 3 (parallel, staggered deadlines)
- Agent 6: Jul 3-10
- Integration: Jul 10-Aug 1 (fixes + final verification)

---

**Prepared for:** 6-agent parallel dispatch  
**Execution model:** TDD-first, independent domains, zero overlap  
**Status:** Ready for dispatch
