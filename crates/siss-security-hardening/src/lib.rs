pub mod encryption;
pub mod audit_trail;
pub mod access_control;
pub mod certificate_management;
pub mod compliance;

pub use encryption::{
    CapsuleEncryption, EncryptionError, EncryptedPayload, KeyManager,
};
pub use audit_trail::{
    AuditTrail, AuditLogEntry, TamperDetectionError, SignatureVerifier,
};
pub use access_control::{
    AccessControl, AccessControlError, CustomerNamespace, Permission, Role,
};
pub use certificate_management::{
    CertificateManager, CertificateError, TLSConfig,
};
pub use compliance::{
    ComplianceChecker, ComplianceStatus, AnnexIIIRequirement,
};

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_encryption_roundtrip() {
        let key = KeyManager::generate_key();
        let encryption = CapsuleEncryption::new(key.clone());

        let plaintext = b"sensitive capsule data";
        let encrypted = encryption.encrypt(plaintext).expect("Encrypt should succeed");
        let decrypted = encryption.decrypt(&encrypted).expect("Decrypt should succeed");

        assert_eq!(plaintext, decrypted.as_slice());
    }

    #[test]
    fn test_encryption_fails_without_key() {
        let key = KeyManager::generate_key();
        let encryption = CapsuleEncryption::new(key);

        let plaintext = b"secret";
        let encrypted = encryption.encrypt(plaintext).expect("Encrypt should succeed");

        // Create a new encryption instance with different key
        let different_key = KeyManager::generate_key();
        let different_encryption = CapsuleEncryption::new(different_key);

        let result = different_encryption.decrypt(&encrypted);
        assert!(result.is_err(), "Decryption with wrong key must fail");
    }

    #[test]
    fn test_access_control_isolation() {
        let mut access_control = AccessControl::new();
        let customer_a = CustomerNamespace::new("customer_a".to_string());
        let customer_b = CustomerNamespace::new("customer_b".to_string());

        access_control.grant_permission(
            customer_a.clone(),
            Permission::Query,
            Role::Admin,
        ).expect("Grant should succeed");

        // Customer A should not be able to query Customer B data
        let can_access = access_control.check_access(
            &customer_a,
            &customer_b,
            Permission::Query,
        );
        assert!(!can_access, "Cross-customer access must be denied");
    }

    #[test]
    fn test_audit_trail_signature() {
        let audit = AuditTrail::new();
        let entry = AuditLogEntry::new_operation(
            Uuid::new_v4(),
            "capsule_commit",
            "success",
        );

        let signed_entry = audit.sign_entry(&entry).expect("Sign should succeed");
        let verified = audit.verify_signature(&signed_entry).expect("Verify should succeed");

        assert_eq!(verified.operation, "capsule_commit");
    }

    #[test]
    fn test_audit_trail_tamper_detection() {
        let audit = AuditTrail::new();
        let entry = AuditLogEntry::new_operation(
            Uuid::new_v4(),
            "capsule_commit",
            "success",
        );

        let mut signed_entry = audit.sign_entry(&entry).expect("Sign should succeed");

        // Simulate tampering by changing status
        signed_entry.status = "modified".to_string();

        let result = audit.verify_signature(&signed_entry);
        assert!(result.is_err(), "Tampered signature must be detected");
    }
}
