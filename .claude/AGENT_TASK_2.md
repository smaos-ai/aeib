# AGENT 2: Regional Compliance Framework
**Dispatch Date:** 2026-06-07 (after Agent 1 completes)  
**Deadline:** 2026-06-12 (5 days)  
**TDD Discipline:** ✅ REQUIRED — Write tests first, ALL FAILING, then implement

---

## Your Task

Build the regional compliance registry covering 5 APAC countries:
- 🇸🇬 Singapore PDPA (Personal Data Protection Act)
- 🇦🇺 Australia Privacy Act
- 🇯🇵 Japan APPI (Act on Protection of Personal Information)
- 🇰🇷 South Korea PIPA (Personal Information Protection Act)
- 🇮🇳 India DPDP (Digital Personal Data Protection Act)

## Files You Own (EXCLUSIVE)
- `crates/siss-apac-expansion/src/compliance/mod.rs` (create)
- `crates/siss-apac-expansion/src/compliance/rules.rs` (create)
- `crates/siss-apac-expansion/src/compliance/validator.rs` (create)
- `crates/siss-apac-expansion/migrations/001_compliance_registry.sql` (create)
- `crates/siss-apac-expansion/src/tests.rs` (ADD ONLY compliance_tests module)

**DO NOT TOUCH:** Other test modules (settlement, localization, etc.)

---

## TDD Execution Order

### Step 1: Write ALL Tests First (Should Fail)

**File:** `crates/siss-apac-expansion/src/tests.rs` — ADD this entire module:

```rust
#[cfg(test)]
mod compliance_tests {
    use crate::compliance::{ComplianceRegistry, ComplianceValidator, Country, UserRight};

    #[test]
    fn test_regional_compliance_coverage() {
        let registry = ComplianceRegistry::new();
        
        let countries = vec!["SG", "AU", "JP", "KR", "IN"];
        for code in countries {
            let req = registry.get_requirement(code);
            assert!(
                req.is_some(),
                "Country code {} should have compliance requirements",
                code
            );
        }

        let all = registry.all_countries();
        assert_eq!(all.len(), 5, "Should have 5 countries");
    }

    #[test]
    fn test_singapore_pdpa_requirements() {
        let registry = ComplianceRegistry::new();
        let sg = registry.get_requirement("SG").unwrap();
        
        assert_eq!(sg.country, Country::Singapore);
        assert!(sg.data_residency_required);
        assert_eq!(sg.residency_location, Some("Singapore".to_string()));
        assert!(sg.dpia_required);
        assert!(sg.user_rights.contains(&UserRight::Access));
    }

    #[test]
    fn test_australia_privacy_act() {
        let registry = ComplianceRegistry::new();
        let au = registry.get_requirement("AU").unwrap();
        
        assert_eq!(au.country, Country::Australia);
        assert!(au.data_residency_required);
        assert_eq!(au.breach_notification_hours, 48);
    }

    #[test]
    fn test_japan_appi_requirements() {
        let registry = ComplianceRegistry::new();
        let jp = registry.get_requirement("JP").unwrap();
        
        assert_eq!(jp.country, Country::Japan);
        assert!(!jp.data_residency_required);
        assert_eq!(jp.retention_days, 730);
    }

    #[test]
    fn test_korea_pipa_requirements() {
        let registry = ComplianceRegistry::new();
        let kr = registry.get_requirement("KR").unwrap();
        
        assert_eq!(kr.country, Country::Korea);
        assert!(kr.data_residency_required);
        assert!(kr.dpia_required);
    }

    #[test]
    fn test_india_dpdp_requirements() {
        let registry = ComplianceRegistry::new();
        let in_req = registry.get_requirement("IN").unwrap();
        
        assert_eq!(in_req.country, Country::India);
        assert!(in_req.data_residency_required);
        assert!(in_req.user_rights.contains(&UserRight::AutomatedDecisionOpting));
    }

    #[test]
    fn test_data_residency_validation() {
        let registry = ComplianceRegistry::new();
        let sg = registry.get_requirement("SG").unwrap();

        let valid = ComplianceValidator::validate_data_residency(
            &sg.country,
            "Singapore",
            &sg,
        );
        assert!(valid.is_ok());

        let invalid = ComplianceValidator::validate_data_residency(
            &sg.country,
            "Australia",
            &sg,
        );
        assert!(invalid.is_err());
    }

    #[test]
    fn test_full_compliance_validation() {
        let registry = ComplianceRegistry::new();

        let result = registry.validate_full_compliance(
            "SG",
            "Singapore",
            true,
            365,
            &[
                UserRight::Access,
                UserRight::Correction,
                UserRight::Deletion,
                UserRight::PortabilityExport,
            ],
        );

        assert!(result.is_ok());
    }

    #[test]
    fn test_compliance_validation_fails_on_residency() {
        let registry = ComplianceRegistry::new();

        let result = registry.validate_full_compliance(
            "KR",
            "USA",
            true,
            365,
            &[UserRight::Access, UserRight::Deletion],
        );

        assert!(result.is_err());
    }
}
```

**Run tests (should FAIL):**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-apac-expansion compliance_tests 2>&1 | head -50
```

Expected: All 8 tests fail (modules don't exist yet)

---

### Step 2: Implement rules.rs

**File:** `crates/siss-apac-expansion/src/compliance/rules.rs`

```rust
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Country {
    Singapore,
    Australia,
    Japan,
    Korea,
    India,
}

impl Country {
    pub fn code(&self) -> &str {
        match self {
            Country::Singapore => "SG",
            Country::Australia => "AU",
            Country::Japan => "JP",
            Country::Korea => "KR",
            Country::India => "IN",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceRequirement {
    pub country: Country,
    pub regulation_name: String,
    pub data_residency_required: bool,
    pub residency_location: Option<String>,
    pub consent_type: ConsentType,
    pub retention_days: u32,
    pub breach_notification_hours: u32,
    pub dpia_required: bool,
    pub user_rights: Vec<UserRight>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ConsentType {
    OptIn,
    OptOut,
    Explicit,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum UserRight {
    Access,
    Deletion,
    Correction,
    PortabilityExport,
    ObjectionToProcessing,
    AutomatedDecisionOpting,
}

pub fn get_country_requirements(country: &Country) -> ComplianceRequirement {
    match country {
        Country::Singapore => ComplianceRequirement {
            country: Country::Singapore,
            regulation_name: "PDPA (Personal Data Protection Act)".to_string(),
            data_residency_required: true,
            residency_location: Some("Singapore".to_string()),
            consent_type: ConsentType::Explicit,
            retention_days: 365,
            breach_notification_hours: 72,
            dpia_required: true,
            user_rights: vec![
                UserRight::Access,
                UserRight::Correction,
                UserRight::Deletion,
                UserRight::PortabilityExport,
            ],
        },
        Country::Australia => ComplianceRequirement {
            country: Country::Australia,
            regulation_name: "Privacy Act 1988".to_string(),
            data_residency_required: true,
            residency_location: Some("Australia".to_string()),
            consent_type: ConsentType::OptOut,
            retention_days: 730,
            breach_notification_hours: 48,
            dpia_required: false,
            user_rights: vec![
                UserRight::Access,
                UserRight::Correction,
                UserRight::Deletion,
            ],
        },
        Country::Japan => ComplianceRequirement {
            country: Country::Japan,
            regulation_name: "APPI (Act on Protection of Personal Information)".to_string(),
            data_residency_required: false,
            residency_location: None,
            consent_type: ConsentType::OptIn,
            retention_days: 730,
            breach_notification_hours: 24,
            dpia_required: false,
            user_rights: vec![
                UserRight::Access,
                UserRight::Deletion,
                UserRight::PortabilityExport,
            ],
        },
        Country::Korea => ComplianceRequirement {
            country: Country::Korea,
            regulation_name: "PIPA (Personal Information Protection Act)".to_string(),
            data_residency_required: true,
            residency_location: Some("South Korea".to_string()),
            consent_type: ConsentType::OptIn,
            retention_days: 365,
            breach_notification_hours: 24,
            dpia_required: true,
            user_rights: vec![
                UserRight::Access,
                UserRight::Correction,
                UserRight::Deletion,
                UserRight::ObjectionToProcessing,
            ],
        },
        Country::India => ComplianceRequirement {
            country: Country::India,
            regulation_name: "DPDP (Digital Personal Data Protection Act)".to_string(),
            data_residency_required: true,
            residency_location: Some("India".to_string()),
            consent_type: ConsentType::Explicit,
            retention_days: 365,
            breach_notification_hours: 72,
            dpia_required: true,
            user_rights: vec![
                UserRight::Access,
                UserRight::Deletion,
                UserRight::Correction,
                UserRight::PortabilityExport,
                UserRight::AutomatedDecisionOpting,
            ],
        },
    }
}
```

---

### Step 3: Implement validator.rs

**File:** `crates/siss-apac-expansion/src/compliance/validator.rs`

```rust
use super::rules::{ComplianceRequirement, Country, UserRight};
use chrono::{DateTime, Utc};

#[derive(Debug, Clone)]
pub struct ComplianceValidator;

impl ComplianceValidator {
    pub fn validate_data_residency(
        country: &Country,
        data_location: &str,
        requirement: &ComplianceRequirement,
    ) -> Result<bool, String> {
        if !requirement.data_residency_required {
            return Ok(true);
        }

        match requirement.residency_location {
            Some(ref allowed_location) => {
                if data_location.contains(allowed_location) {
                    Ok(true)
                } else {
                    Err(format!(
                        "{:?} requires data residency in {}",
                        country, allowed_location
                    ))
                }
            }
            None => Ok(true),
        }
    }

    pub fn validate_consent_obtained(
        consent_given: bool,
        consent_timestamp: Option<DateTime<Utc>>,
        requirement: &ComplianceRequirement,
    ) -> Result<bool, String> {
        if requirement.data_residency_required || requirement.dpia_required {
            if !consent_given {
                return Err("Explicit consent required".to_string());
            }
        }
        Ok(true)
    }

    pub fn validate_retention_policy(
        retention_days: u32,
        requirement: &ComplianceRequirement,
    ) -> Result<bool, String> {
        if retention_days > requirement.retention_days {
            Err(format!(
                "Retention exceeds maximum of {} days",
                requirement.retention_days
            ))
        } else {
            Ok(true)
        }
    }

    pub fn validate_user_rights_support(
        supported_rights: &[UserRight],
        requirement: &ComplianceRequirement,
    ) -> Result<bool, String> {
        for required_right in &requirement.user_rights {
            if !supported_rights.contains(required_right) {
                return Err(format!("User right {:?} not supported", required_right));
            }
        }
        Ok(true)
    }
}
```

---

### Step 4: Implement mod.rs

**File:** `crates/siss-apac-expansion/src/compliance/mod.rs`

```rust
pub mod rules;
pub mod validator;

pub use rules::{ComplianceRequirement, ConsentType, Country, UserRight, get_country_requirements};
pub use validator::ComplianceValidator;
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct ComplianceRegistry {
    requirements: HashMap<String, ComplianceRequirement>,
}

impl ComplianceRegistry {
    pub fn new() -> Self {
        let mut requirements = HashMap::new();
        
        for country in [
            Country::Singapore,
            Country::Australia,
            Country::Japan,
            Country::Korea,
            Country::India,
        ] {
            let req = get_country_requirements(&country);
            requirements.insert(country.code().to_string(), req);
        }

        ComplianceRegistry { requirements }
    }

    pub fn get_requirement(&self, country_code: &str) -> Option<ComplianceRequirement> {
        self.requirements.get(country_code).cloned()
    }

    pub fn all_countries(&self) -> Vec<ComplianceRequirement> {
        self.requirements.values().cloned().collect()
    }

    pub fn validate_full_compliance(
        &self,
        country_code: &str,
        data_location: &str,
        consent_given: bool,
        retention_days: u32,
        supported_rights: &[UserRight],
    ) -> Result<bool, Vec<String>> {
        let requirement = self
            .get_requirement(country_code)
            .ok_or_else(|| vec!["Unknown country code".to_string()])?;

        let mut errors = Vec::new();

        if let Err(e) = ComplianceValidator::validate_data_residency(
            &requirement.country,
            data_location,
            &requirement,
        ) {
            errors.push(e);
        }

        if let Err(e) = ComplianceValidator::validate_consent_obtained(
            consent_given,
            None,
            &requirement,
        ) {
            errors.push(e);
        }

        if let Err(e) = ComplianceValidator::validate_retention_policy(retention_days, &requirement)
        {
            errors.push(e);
        }

        if let Err(e) =
            ComplianceValidator::validate_user_rights_support(supported_rights, &requirement)
        {
            errors.push(e);
        }

        if errors.is_empty() {
            Ok(true)
        } else {
            Err(errors)
        }
    }
}

impl Default for ComplianceRegistry {
    fn default() -> Self {
        Self::new()
    }
}
```

---

### Step 5: Create Migration File

**File:** `crates/siss-apac-expansion/migrations/001_compliance_registry.sql`

```sql
CREATE TABLE IF NOT EXISTS compliance_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(2) UNIQUE NOT NULL,
    regulation_name VARCHAR(255) NOT NULL,
    data_residency_required BOOLEAN DEFAULT FALSE,
    residency_location VARCHAR(100),
    consent_type VARCHAR(20) NOT NULL,
    retention_days INTEGER NOT NULL,
    breach_notification_hours INTEGER NOT NULL,
    dpia_required BOOLEAN DEFAULT FALSE,
    user_rights JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_compliance_country ON compliance_requirements(country_code);
```

---

### Step 6: Run Tests (Should PASS)

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-apac-expansion compliance_tests
```

**Expected:** ✅ All 8 tests pass

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
git add crates/siss-apac-expansion/src/compliance crates/siss-apac-expansion/migrations/001_compliance_registry.sql crates/siss-apac-expansion/src/tests.rs
git commit -m "feat: regional compliance framework covering 5 APAC countries (PDPA, Privacy Act, APPI, PIPA, DPDP)"
```

---

## Success Criteria

- [x] 8 tests passing
- [x] 5 countries supported (SG, AU, JP, KR, IN)
- [x] All compliance requirements validated
- [x] Clippy clean
- [x] Migration file created
- [x] One commit

---

## Return Summary

```
AGENT 2 COMPLETION SUMMARY
==========================

✅ Regional Compliance Framework
✅ 5 countries covered:
   - Singapore PDPA (explicit consent, Singapore residency)
   - Australia Privacy Act (opt-out, Australia residency)
   - Japan APPI (opt-in, no residency)
   - South Korea PIPA (explicit, DPIA, Korea residency)
   - India DPDP (explicit, DPIA, India residency)

✅ Tests: 8/8 PASSING
✅ Clippy: CLEAN
✅ Migration: 001_compliance_registry.sql

Commit: feat: regional compliance framework...
Git hash: [your hash]

Status: ✅ READY FOR AGENT 3
```
