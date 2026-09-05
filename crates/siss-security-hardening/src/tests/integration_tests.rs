use siss_security_hardening::{
    CapsuleEncryption, KeyManager, EncryptedPayload,
    AuditTrail, AuditLogEntry,
    AccessControl, CustomerNamespace, Permission, Role,
    CertificateManager, TLSConfig,
    ComplianceChecker, ComplianceEvidence, ComplianceStatus, AnnexIIIRequirement,
};
use uuid::Uuid;

#[test]
fn test_full_encryption_pipeline() {
    // Customer A's key
    let key_a = KeyManager::generate_key();
    let cipher_a = CapsuleEncryption::new(key_a.clone());

    // Customer B's key (different)
    let key_b = KeyManager::generate_key();
    let cipher_b = CapsuleEncryption::new(key_b.clone());

    let capsule_data = b"Customer A sensitive capsule";

    // Encrypt with A's key
    let encrypted = cipher_a.encrypt(capsule_data)
        .expect("Encryption should succeed");

    // A can decrypt
    let decrypted_a = cipher_a.decrypt(&encrypted)
        .expect("A should decrypt own data");
    assert_eq!(decrypted_a, capsule_data);

    // B cannot decrypt (wrong key)
    let result_b = cipher_b.decrypt(&encrypted);
    assert!(result_b.is_err(), "B should not decrypt A's data");
}

#[test]
fn test_access_control_with_audit_trail() {
    let mut access_control = AccessControl::new();
    let mut audit = AuditTrail::new();

    let customer_a = CustomerNamespace::new("customer_a".to_string());
    let customer_b = CustomerNamespace::new("customer_b".to_string());

    // Grant A admin privileges
    access_control.grant_permission(
        customer_a.clone(),
        Permission::Query,
        Role::Admin,
    ).expect("Grant should succeed");

    // Log the permission grant
    let grant_entry = AuditLogEntry::new_operation(
        Uuid::new_v4(),
        "permission_grant",
        "success",
    );
    audit.add_entry(grant_entry).expect("Add entry");

    // A can query
    assert!(access_control.check_access(
        &customer_a,
        &customer_a,
        Permission::Query
    ));

    // B cannot query A's data
    assert!(!access_control.check_access(
        &customer_b,
        &customer_a,
        Permission::Query
    ));

    // Verify audit trail
    assert_eq!(audit.entries().len(), 1);
}

#[test]
fn test_certificate_pinning_workflow() {
    let mut tls_config = TLSConfig::tls_13_with_mtls();
    tls_config.certificate_pinning = true;

    let mut cert_manager = CertificateManager::new(tls_config)
        .expect("Create manager");

    // Generate certificate for agent-01
    let cert = cert_manager
        .generate_self_signed("agent-01.sovereignnexus.com", 365)
        .expect("Generate certificate");

    // Store it
    cert_manager.store_certificate(cert.clone())
        .expect("Store certificate");

    // Pin it
    cert_manager.pin_certificate(&cert);

    // Validate it works
    let validation = cert_manager.validate_certificate_for_hostname(
        &cert,
        "agent-01.sovereignnexus.com",
    );
    assert!(validation.is_ok(), "Valid certificate should pass validation");

    // Try with wrong hostname
    let wrong_host = cert_manager.validate_certificate_for_hostname(
        &cert,
        "agent-02.sovereignnexus.com",
    );
    assert!(wrong_host.is_err(), "Wrong hostname should fail");
}

#[test]
fn test_compliance_audit_readiness() {
    let mut compliance = ComplianceChecker::new();

    // Record evidence for all critical requirements
    let requirements = vec![
        (AnnexIIIRequirement::HighRiskSystemClassification, "System is high-risk per Annex III"),
        (AnnexIIIRequirement::RiskAssessmentAndMitigation, "Comprehensive risk register completed"),
        (AnnexIIIRequirement::HumanOversightProcedures, "φ+ Eval Court implemented"),
        (AnnexIIIRequirement::TransparencyAndExplainability, "Decision logs available"),
        (AnnexIIIRequirement::DocumentationAndTechnicalRecords, "Full SISS spec v2.0"),
        (AnnexIIIRequirement::DataGovernanceAndQuality, "GDPR-aligned policies"),
        (AnnexIIIRequirement::PerformanceMonitoring, "Real-time dashboard active"),
        (AnnexIIIRequirement::CybersecurityAndRobustness, "AES-256 + TLS 1.3 implemented"),
        (AnnexIIIRequirement::CorrectiveActionsMechanism, "Incident response plan active"),
    ];

    for (req, description) in requirements {
        compliance.record_evidence(ComplianceEvidence {
            requirement: req,
            status: ComplianceStatus::Met,
            evidence_description: description.to_string(),
            verification_date: "2026-05-27".to_string(),
            responsible_team: "Security Team".to_string(),
        });
    }

    // All critical requirements met
    assert!(compliance.are_critical_requirements_met());

    // 100% compliance score
    assert_eq!(compliance.overall_compliance_score(), 100.0);
}

#[test]
fn test_end_to_end_secure_capsule_workflow() {
    // Setup
    let master_key = KeyManager::generate_key();
    let customer_key = KeyManager::derive_key_for_customer(&master_key, "customer_prod");
    let cipher = CapsuleEncryption::new(customer_key);

    let mut audit = AuditTrail::new();
    let mut access_control = AccessControl::new();

    let customer = CustomerNamespace::new("customer_prod".to_string());

    // Step 1: Grant access
    access_control.grant_permission(
        customer.clone(),
        Permission::Query,
        Role::Operator,
    ).expect("Grant");

    // Step 2: Create capsule
    let capsule_id = Uuid::new_v4();
    let capsule_data = b"Sensitive agent state: task_id=123, status=executing";

    // Step 3: Encrypt capsule
    let encrypted_capsule = cipher.encrypt(capsule_data)
        .expect("Encrypt");

    // Step 4: Log operation
    let mut entry = AuditLogEntry::new_operation(
        capsule_id,
        "capsule_create",
        "success",
    );
    entry.actor = "agent_001".to_string();

    let signed_entry = audit.sign_entry(&entry)
        .expect("Sign entry");
    audit.add_entry(signed_entry).expect("Add to audit");

    // Step 5: Verify access
    assert!(access_control.check_access(
        &customer,
        &customer,
        Permission::Query
    ));

    // Step 6: Decrypt capsule
    let decrypted = cipher.decrypt(&encrypted_capsule)
        .expect("Decrypt");

    // Step 7: Verify audit integrity
    let stored_entries = audit.entries();
    assert!(audit.verify_chain_integrity(stored_entries)
        .expect("Chain verify") == true);

    // Assertions
    assert_eq!(decrypted, capsule_data);
    assert_eq!(audit.entries().len(), 1);
}

#[test]
fn test_cross_region_encryption_key_derivation() {
    let master_key = KeyManager::generate_key();

    // Different regions derive different keys from same master
    let key_us_west = KeyManager::derive_key_for_customer(&master_key, "region:us-west");
    let key_eu_central = KeyManager::derive_key_for_customer(&master_key, "region:eu-central");
    let key_ap_southeast = KeyManager::derive_key_for_customer(&master_key, "region:ap-southeast");

    // Keys are different
    assert_ne!(key_us_west.as_bytes(), key_eu_central.as_bytes());
    assert_ne!(key_eu_central.as_bytes(), key_ap_southeast.as_bytes());

    // Deterministic: same derivation yields same key
    let key_us_west_again = KeyManager::derive_key_for_customer(&master_key, "region:us-west");
    assert_eq!(key_us_west.as_bytes(), key_us_west_again.as_bytes());

    // Can encrypt/decrypt with each independently
    let cipher_us = CapsuleEncryption::new(key_us_west);
    let data = b"multi-region test";
    let encrypted = cipher_us.encrypt(data).expect("Encrypt");
    let decrypted = cipher_us.decrypt(&encrypted).expect("Decrypt");
    assert_eq!(decrypted, data);
}

#[test]
fn test_audit_trail_chain_tampering_detection() {
    let mut audit = AuditTrail::new();
    let capsule_id = Uuid::new_v4();

    // Create 3 entries
    for i in 0..3 {
        let entry = AuditLogEntry::new_operation(
            capsule_id,
            &format!("operation_{}", i),
            "success",
        );
        audit.add_entry(entry).expect("Add entry");
    }

    let original_entries = audit.entries().to_vec();

    // Verify original chain is valid
    assert!(audit.verify_chain_integrity(&original_entries)
        .expect("Chain verify") == true);

    // Try to tamper with middle entry
    let mut tampered = original_entries.clone();
    if let Some(middle) = tampered.get_mut(1) {
        middle.status = "tampered".to_string();
    }

    // Tampering detection (signature will not match)
    let result = audit.verify_chain_integrity(&tampered);
    assert!(result.is_err(), "Tampered entry should fail verification");
}

#[test]
fn test_tls_configuration_for_mltls() {
    let tls_config = TLSConfig::tls_13_with_mtls();

    // Verify TLS 1.3
    assert_eq!(tls_config.tls_version, "1.3");

    // mTLS enabled
    assert!(tls_config.enable_mtls);

    // Certificate pinning enabled
    assert!(tls_config.certificate_pinning);

    // Modern cipher suites only
    assert_eq!(tls_config.cipher_suites.len(), 2);
    assert!(tls_config.cipher_suites.contains(&"TLS_AES_256_GCM_SHA384".to_string()));

    // Validation passes
    assert!(tls_config.validate().is_ok());
}
