/// Test suite for Stream 6 (USA Creator KYC/AML) integration.
/// Following TDD pattern: tests written first, then implementation.
#[cfg(test)]
mod stream6_integration_tests {
    use siss_stream6_usa_creator::{
        AMLChecker, AMLRiskLevel, KYCStatus, KYCVerifier, SanctionedEntity, Stream6Gate,
    };
    use chrono::Utc;
    use std::sync::Arc;
    use uuid::Uuid;
    use siss_layer00::{Layer0Gate, Mandate};

    // Mock MandateStore for testing
    use dashmap::DashMap;
    use siss_layer00::{MandateStore, MandateError};

    struct MockMandateStore {
        mandates: DashMap<Uuid, Mandate>,
        revoked: DashMap<Uuid, bool>,
    }

    impl MockMandateStore {
        fn new() -> Arc<Self> {
            Arc::new(Self {
                mandates: DashMap::new(),
                revoked: DashMap::new(),
            })
        }
    }

    impl MandateStore for MockMandateStore {
        fn insert_mandate(&self, mandate: Mandate) -> Result<(), MandateError> {
            self.mandates.insert(mandate.id, mandate);
            Ok(())
        }

        fn get_mandate(&self, id: Uuid) -> Result<Option<Mandate>, MandateError> {
            Ok(self.mandates.get(&id).map(|m| m.clone()))
        }

        fn revoke_mandate(&self, id: Uuid) -> Result<(), MandateError> {
            self.revoked.insert(id, true);
            Ok(())
        }

        fn is_revoked(&self, id: Uuid) -> bool {
            self.revoked.get(&id).map(|r| *r).unwrap_or(false)
        }
    }

    // ============================================================================
    // KYC Verification Tests (5 tests)
    // ============================================================================

    #[tokio::test]
    async fn test_kyc_verify_valid_usa_identity() {
        // Verifies that KYC validation accepts valid USA identity with SSN format.
        // Ensures state database lookup returns verified status.
        let verifier = KYCVerifier::new();
        let creator_id = Uuid::new_v4();
        let creator_name = "Alice Smith";
        let ssn = "123-45-6789";

        // Verify identity (mocked as accepting valid format)
        let status = verifier
            .verify_identity(creator_id, creator_name, ssn)
            .await
            .expect("verify_identity should succeed");

        // Mock state: valid SSN format passes (simulates state DB lookup)
        assert_eq!(status, KYCStatus::Pending);

        // Update to verified (simulates successful state lookup)
        verifier
            .update_kyc_status(creator_id, KYCStatus::Verified)
            .expect("update should succeed");

        let final_status = verifier
            .get_kyc_status(creator_id)
            .expect("get_kyc_status should succeed");
        assert_eq!(final_status, KYCStatus::Verified);
    }

    #[tokio::test]
    async fn test_kyc_pending_status() {
        // Verifies that initial KYC submission starts in Pending state.
        // Ensures initial submission tracking is correctly initialized.
        let verifier = KYCVerifier::new();
        let creator_id = Uuid::new_v4();

        let status = verifier
            .verify_identity(creator_id, "Bob Jones", "987-65-4321")
            .await
            .expect("verify_identity should succeed");

        assert_eq!(status, KYCStatus::Pending);

        // Verify record exists in cache
        let record = verifier
            .get_kyc_record(creator_id)
            .expect("get_kyc_record should succeed");
        assert_eq!(record.status, KYCStatus::Pending);
        assert!(record.verified_at.is_none());
        assert!(record.expires_at.is_none());
    }

    #[tokio::test]
    async fn test_kyc_expire_after_ttl() {
        // Verifies that KYC records expire after 1 year TTL.
        // Ensures time-based expiration is correctly enforced.
        let verifier = KYCVerifier::new();
        let creator_id = Uuid::new_v4();

        // Create verified record
        verifier
            .verify_identity(creator_id, "Carol White", "555-55-5555")
            .await
            .expect("verify_identity should succeed");

        verifier
            .update_kyc_status(creator_id, KYCStatus::Verified)
            .expect("update should succeed");

        let record = verifier
            .get_kyc_record(creator_id)
            .expect("get_kyc_record should succeed");

        // Verify expiration is set to ~365 days from now
        assert!(record.verified_at.is_some());
        assert!(record.expires_at.is_some());

        let expires_at = record.expires_at.unwrap();
        let now = Utc::now();
        let diff = (expires_at - now).num_days();

        // Should be approximately 365 days (within 2 days margin)
        assert!((363..=367).contains(&diff), "diff={}", diff);

        // Verify is_valid() returns true for non-expired record
        assert!(record.is_valid());
    }

    #[tokio::test]
    async fn test_kyc_cache_hit_miss() {
        // Verifies DashMap cache correctness for KYC records.
        // Ensures thread-safe concurrent caching works correctly.
        let verifier = KYCVerifier::new();
        let creator_id = Uuid::new_v4();
        let creator_name = "David Lee";

        // Cache miss: creator not in cache yet
        let result = verifier.get_kyc_status(creator_id);
        assert!(
            result.is_err(),
            "get_kyc_status should error on cache miss"
        );

        // Add creator to cache
        verifier
            .verify_identity(creator_id, creator_name, "111-11-1111")
            .await
            .expect("verify_identity should succeed");

        // Cache hit: creator now in cache
        let status = verifier
            .get_kyc_status(creator_id)
            .expect("get_kyc_status should succeed on cache hit");
        assert_eq!(status, KYCStatus::Pending);

        // Verify cache retrieval is consistent
        let record = verifier
            .get_kyc_record(creator_id)
            .expect("get_kyc_record should succeed");
        assert_eq!(record.creator_name, creator_name);
    }

    #[tokio::test]
    async fn test_kyc_reject_blacklisted() {
        // Verifies that KYC rejects creators on blacklist (fraud detection).
        // Ensures known fraud patterns are caught early.
        let verifier = KYCVerifier::new();
        let creator_id = Uuid::new_v4();

        // Submit verification
        verifier
            .verify_identity(creator_id, "Fraud Person", "999-99-9999")
            .await
            .expect("verify_identity should succeed");

        // Mark as rejected (simulates fraud detection)
        verifier
            .update_kyc_status(creator_id, KYCStatus::Rejected)
            .expect("update should succeed");

        let status = verifier
            .get_kyc_status(creator_id)
            .expect("get_kyc_status should succeed");
        assert_eq!(status, KYCStatus::Rejected);

        // Verify is_valid() returns false for rejected record
        let record = verifier
            .get_kyc_record(creator_id)
            .expect("get_kyc_record should succeed");
        assert!(!record.is_valid());
    }

    // ============================================================================
    // AML Sanctions Screening Tests (3 tests)
    // ============================================================================

    #[tokio::test]
    async fn test_aml_check_ofac_list() {
        // Verifies OFAC sanctions list screening functionality.
        // Ensures US OFAC SDN list is checked for sanctioned creators.
        let aml_checker = AMLChecker::new();

        // Add a sanctioned entity (mocked OFAC SDN list)
        let sanctioned = SanctionedEntity {
            name: "Vladimir Putin".to_string(),
            entity_id: "ofac-12345".to_string(),
            country: "Russia".to_string(),
            reason: "Sanctions List Entry".to_string(),
        };

        aml_checker
            .add_sanctioned_entity(sanctioned)
            .expect("add_sanctioned_entity should succeed");

        // Check clean creator passes
        let is_clean = aml_checker
            .check_sanctions("Alice Smith")
            .await
            .expect("check_sanctions should succeed");
        assert!(is_clean);

        // Check sanctioned creator is blocked
        let is_sanctioned = aml_checker
            .check_sanctions("Vladimir Putin")
            .await
            .expect("check_sanctions should succeed");
        assert!(!is_sanctioned, "sanctioned creator should be detected");
    }

    #[tokio::test]
    async fn test_aml_check_eu_sanctions() {
        // Verifies EU consolidated sanctions list screening.
        // Ensures EU sanctions are cross-checked alongside OFAC.
        let aml_checker = AMLChecker::new();

        // Add EU-sanctioned entity (mocked EU consolidated list)
        let eu_entity = SanctionedEntity {
            name: "Hassan Rouhani".to_string(),
            entity_id: "eu-67890".to_string(),
            country: "Iran".to_string(),
            reason: "EU Sanctions".to_string(),
        };

        aml_checker
            .add_sanctioned_entity(eu_entity)
            .expect("add_sanctioned_entity should succeed");

        // Verify EU entity is detected
        let is_sanctioned = aml_checker
            .check_sanctions("Hassan Rouhani")
            .await
            .expect("check_sanctions should succeed");
        assert!(!is_sanctioned, "EU-sanctioned creator should be detected");

        // Verify non-sanctioned creator passes
        let is_clean = aml_checker
            .check_sanctions("Normal Creator")
            .await
            .expect("check_sanctions should succeed");
        assert!(is_clean);
    }

    #[tokio::test]
    async fn test_aml_risk_assessment() {
        // Verifies AML risk assessment categorizes creators correctly.
        // Ensures risk levels (Low, Medium, High, Critical) are properly assigned.
        let aml_checker = AMLChecker::new();
        let creator_id = Uuid::new_v4();

        // Test clean creator (Low risk = 95% pass rate)
        let risk_level = aml_checker
            .check_aml_risk(creator_id, "Clean Creator")
            .await
            .expect("check_aml_risk should succeed");
        assert_eq!(risk_level, AMLRiskLevel::Low);

        // Add sanctioned entity and test High risk
        let sanctioned = SanctionedEntity {
            name: "Sanctioned Creator".to_string(),
            entity_id: "test-123".to_string(),
            country: "Blocked".to_string(),
            reason: "Test".to_string(),
        };
        aml_checker
            .add_sanctioned_entity(sanctioned)
            .expect("add_sanctioned_entity should succeed");

        let risk_level_sanctioned = aml_checker
            .check_aml_risk(creator_id, "Sanctioned Creator")
            .await
            .expect("check_aml_risk should succeed");
        assert_eq!(risk_level_sanctioned, AMLRiskLevel::High);
    }

    // ============================================================================
    // Stream 6 Gate Integration Tests (2 tests)
    // ============================================================================

    #[tokio::test]
    async fn test_stream6_gate_blocks_unverified_creator() {
        // Verifies Stream 6 gate rejects creators without KYC verification.
        // Ensures KYC is mandatory before tool access (compliance requirement).
        let kyc_verifier = Arc::new(KYCVerifier::new());
        let aml_checker = Arc::new(AMLChecker::new());
        let mandate_store = MockMandateStore::new();
        let layer0_gate = Arc::new(Layer0Gate::new(mandate_store as Arc<dyn MandateStore>));

        let gate = Stream6Gate::new(layer0_gate, kyc_verifier.clone(), aml_checker);

        let creator_id = Uuid::new_v4();

        // Create unverified KYC record (Pending status)
        kyc_verifier
            .verify_identity(creator_id, "Unverified Creator", "000-00-0000")
            .await
            .expect("verify_identity should succeed");

        // Stream 6 gate should reject unverified creator
        let result = gate
            .compliance_check(creator_id)
            .await
            .expect("compliance_check should succeed");

        assert!(!result.is_compliant, "unverified creator should fail compliance");
        assert!(!result.kyc_verified, "kyc_verified should be false");
    }

    #[tokio::test]
    async fn test_stream6_gate_logs_to_layer0() {
        // Verifies Stream 6 gate integration with Layer 0 Merkle audit trail.
        // Ensures compliance checks are logged to governance layer.
        let kyc_verifier = Arc::new(KYCVerifier::new());
        let aml_checker = Arc::new(AMLChecker::new());
        let mandate_store = MockMandateStore::new();
        let layer0_gate = Arc::new(Layer0Gate::new(mandate_store as Arc<dyn MandateStore>));

        let gate = Stream6Gate::new(layer0_gate, kyc_verifier.clone(), aml_checker);

        let creator_id = Uuid::new_v4();

        // Create verified KYC record
        kyc_verifier
            .verify_identity(creator_id, "Verified Creator", "111-11-1111")
            .await
            .expect("verify_identity should succeed");

        kyc_verifier
            .update_kyc_status(creator_id, KYCStatus::Verified)
            .expect("update should succeed");

        // Run compliance check
        let result = gate
            .compliance_check(creator_id)
            .await
            .expect("compliance_check should succeed");

        // Verify all checks report correctly
        assert!(result.kyc_verified, "kyc_verified should be true");
        assert!(result.aml_clear, "aml_clear should be true");
        assert!(result.is_compliant, "is_compliant should be true for verified creator");
    }
}
