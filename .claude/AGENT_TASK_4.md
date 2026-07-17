# AGENT 4: Creator SDK Localization Framework
**Dispatch Date:** 2026-06-19 (after Agent 1 completes)  
**Deadline:** 2026-06-26 (7 days)  
**TDD Discipline:** ✅ REQUIRED — Write tests first

---

## Your Task

Build 5-language SDK localization (Mandarin Chinese, Japanese, Korean, Hindi, Vietnamese) with region-specific onboarding flows for all 5 primary markets.

## Files You Own (EXCLUSIVE)
- `crates/siss-apac-expansion/src/localization/mod.rs` (create)
- `crates/siss-apac-expansion/src/localization/translator.rs` (create)
- `crates/siss-apac-expansion/src/localization/onboarding_flows.rs` (create)
- `crates/siss-apac-expansion/migrations/003_localization_strings.sql` (create)
- `crates/siss-apac-expansion/src/tests.rs` (ADD ONLY localization_tests module)

**DO NOT TOUCH:** Other test modules, other files

---

## TDD Execution Order

### Step 1: Write ALL Tests First (Should Fail)

**File:** `crates/siss-apac-expansion/src/tests.rs` — ADD this module (use exact code from plan, ~140 lines)

Paste from line 1529-1667 of the plan document (test_sdk_localization_complete through test_localization_framework).

**Run tests (should FAIL):**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-apac-expansion localization_tests 2>&1 | head -50
```

Expected: All 12 tests fail

---

### Step 2: Implement translator.rs

**File:** `crates/siss-apac-expansion/src/localization/translator.rs`

Use exact code from plan (lines 1056-1236: Language enum through create_sdk_translations function).

Key components:
- `Language` enum with 5 variants (MandarinChinese, Japanese, Korean, Hindi, Vietnamese)
- `TranslationEntry` struct
- `LocalizationTranslator` with translation storage
- `create_sdk_translations()` function with welcome, onboarding, compliance strings

---

### Step 3: Implement onboarding_flows.rs

**File:** `crates/siss-apac-expansion/src/localization/onboarding_flows.rs`

Use exact code from plan (lines 1240-1454: OnboardingFlow struct through RegionalOnboardingFlowGenerator).

Key components:
- `OnboardingFlow` struct
- `OnboardingStep` struct
- `RegionalOnboardingFlowGenerator` with flows for SG, AU, JP, KR, IN
- Each flow has 3 steps with compliance notes

---

### Step 4: Implement mod.rs

**File:** `crates/siss-apac-expansion/src/localization/mod.rs`

Use exact code from plan (lines 1456-1492: module declarations through LocalizationFramework).

Key components:
- Module re-exports
- `LocalizationFramework` struct wrapping translator
- Methods: get_translation, get_onboarding_flow, export_language_pack

---

### Step 5: Create Migration File

**File:** `crates/siss-apac-expansion/migrations/003_localization_strings.sql`

Use exact SQL from plan (lines 1496-1522).

```sql
CREATE TABLE IF NOT EXISTS localization_strings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(255) NOT NULL,
    language_code VARCHAR(5) NOT NULL,
    value TEXT NOT NULL,
    context VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(key, language_code)
);

CREATE TABLE IF NOT EXISTS onboarding_flows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region_code VARCHAR(2) NOT NULL,
    language_code VARCHAR(5) NOT NULL,
    flow_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(region_code, language_code)
);

CREATE INDEX idx_localization_language ON localization_strings(language_code);
CREATE INDEX idx_onboarding_region ON onboarding_flows(region_code);
```

---

### Step 6: Run Tests (Should PASS)

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-apac-expansion localization_tests
```

**Expected:** ✅ All 12 tests pass

---

### Step 7: Run Clippy

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo clippy -p siss-apac-expansion --all-targets
```

**Expected:** ✅ No warnings

---

### Step 8: Commit

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
git add crates/siss-apac-expansion/src/localization crates/siss-apac-expansion/migrations/003_localization_strings.sql crates/siss-apac-expansion/src/tests.rs
git commit -m "feat: SDK localization framework with 5 languages (Mandarin, Japanese, Korean, Hindi, Vietnamese) and region-specific onboarding flows"
```

---

## Success Criteria

- [x] 12 tests passing
- [x] 5 languages fully translated (welcome, onboarding, compliance strings)
- [x] 5 region-specific onboarding flows (SG, AU, JP, KR, IN)
- [x] Each flow has 3 steps with compliance notes
- [x] Clippy clean
- [x] Migration file created
- [x] One commit

---

## Return Summary

```
AGENT 4 COMPLETION SUMMARY
==========================

✅ Creator SDK Localization Framework
✅ 5 languages:
   - Mandarin Chinese (zh)
   - Japanese (ja)
   - Korean (ko)
   - Hindi (hi)
   - Vietnamese (vi)

✅ Region-specific onboarding flows:
   - Singapore (PDPA compliance notes)
   - Australia (Privacy Act compliance)
   - Japan (APPI compliance)
   - South Korea (PIPA + DPIA notes)
   - India (DPDP + residency notes)

✅ Tests: 12/12 PASSING
✅ Translation strings included
✅ Clippy: CLEAN
✅ Migration: 003_localization_strings.sql

Commit: feat: SDK localization framework...
Git hash: [your hash]

Status: ✅ READY FOR AGENT 5
```
