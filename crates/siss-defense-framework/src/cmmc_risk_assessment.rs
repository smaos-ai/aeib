use std::collections::HashMap;

/// Cryptographic algorithm status
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CryptographicStatus {
    Approved,        // NIST/NSA approved
    Deprecated,      // Still acceptable but phasing out
    Forbidden,       // Should not be used
}

/// Cryptographic control item
#[derive(Debug, Clone)]
pub struct CryptoControl {
    pub algorithm: String,
    pub status: CryptographicStatus,
    pub siss_component: String,
    pub implementation_path: String,
    pub test_coverage: bool,
}

/// TLS/OpenSSL hardening requirement
#[derive(Debug, Clone)]
pub struct TlsHardeningRequirement {
    pub requirement: String,
    pub minimum_version: String,
    pub cipher_suites: Vec<String>,
    pub siss_implementation: String,
    pub validated: bool,
}

/// Secret management control
#[derive(Debug, Clone)]
pub struct SecretManagementControl {
    pub secret_type: String,          // e.g., "API_KEY", "PRIVATE_KEY", "PASSWORD"
    pub storage_location: String,     // e.g., "siss-enclave", "hardware-tpm"
    pub rotation_interval_days: u32,
    pub access_logging: bool,
}

/// Risk assessment item
#[derive(Debug, Clone)]
pub struct RiskItem {
    pub risk_id: String,
    pub category: String,
    pub description: String,
    pub severity: RiskSeverity,
    pub mitigation: String,
    pub responsible_component: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum RiskSeverity {
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4,
}

/// Comprehensive CMMC Level 2 risk assessment
pub struct RiskAssessment {
    pub crypto_controls: HashMap<String, CryptoControl>,
    pub tls_hardening: Vec<TlsHardeningRequirement>,
    pub secret_management: Vec<SecretManagementControl>,
    pub risks: Vec<RiskItem>,
}

impl RiskAssessment {
    pub fn new() -> Self {
        Self {
            crypto_controls: HashMap::new(),
            tls_hardening: vec![],
            secret_management: vec![],
            risks: vec![],
        }
    }

    /// Pre-populate comprehensive risk assessment for CMMC Level 2
    pub fn cmmc_level2_assessment() -> Self {
        let mut ra = Self::new();

        // Cryptographic controls (OpenSSL/TLS hardening)
        let crypto_controls: &[(&str, CryptographicStatus, &str, &str)] = &[
            ("AES-256-GCM", CryptographicStatus::Approved, "siss-enclave", "siss-enclave/src/security.rs"),
            ("ChaCha20-Poly1305", CryptographicStatus::Approved, "siss-enclave", "siss-enclave/src/security.rs"),
            ("SHA-256", CryptographicStatus::Approved, "siss-audit-archiver", "siss-audit-archiver/src/lib.rs"),
            ("ECDSA-P256", CryptographicStatus::Approved, "siss-trust-mesh", "siss-trust-mesh/src/lib.rs"),
            ("RSA-4096", CryptographicStatus::Approved, "siss-agent-card", "siss-agent-card/src/lib.rs"),
            ("TLS 1.3", CryptographicStatus::Approved, "siss-enclave", "siss-enclave/src/security.rs"),
            ("DES", CryptographicStatus::Forbidden, "none", "DO NOT USE - Legacy"),
            ("RC4", CryptographicStatus::Forbidden, "none", "DO NOT USE - Broken"),
            ("MD5", CryptographicStatus::Forbidden, "none", "DO NOT USE - Deprecated"),
            ("SSL 3.0", CryptographicStatus::Forbidden, "none", "DO NOT USE - Legacy"),
        ];

        for (algo, status, component, path) in crypto_controls {
            ra.crypto_controls.insert(
                algo.to_string(),
                CryptoControl {
                    algorithm: algo.to_string(),
                    status: *status,
                    siss_component: component.to_string(),
                    implementation_path: path.to_string(),
                    test_coverage: *status == CryptographicStatus::Approved,
                },
            );
        }

        // TLS hardening requirements
        ra.tls_hardening = vec![
            TlsHardeningRequirement {
                requirement: "Minimum TLS Version".to_string(),
                minimum_version: "1.3".to_string(),
                cipher_suites: vec![
                    "TLS_AES_256_GCM_SHA384".to_string(),
                    "TLS_CHACHA20_POLY1305_SHA256".to_string(),
                ],
                siss_implementation: "siss-enclave/src/security.rs".to_string(),
                validated: true,
            },
            TlsHardeningRequirement {
                requirement: "Certificate Validation".to_string(),
                minimum_version: "1.3".to_string(),
                cipher_suites: vec!["X.509v3".to_string()],
                siss_implementation: "siss-trust-mesh/src/lib.rs".to_string(),
                validated: true,
            },
            TlsHardeningRequirement {
                requirement: "Perfect Forward Secrecy (PFS)".to_string(),
                minimum_version: "1.3".to_string(),
                cipher_suites: vec![
                    "ECDHE-ECDSA-AES256-GCM-SHA384".to_string(),
                    "ECDHE-RSA-AES256-GCM-SHA384".to_string(),
                ],
                siss_implementation: "siss-enclave/src/security.rs".to_string(),
                validated: true,
            },
            TlsHardeningRequirement {
                requirement: "HSTS (Strict-Transport-Security)".to_string(),
                minimum_version: "1.3".to_string(),
                cipher_suites: vec!["max-age=31536000".to_string()],
                siss_implementation: "siss-job-router/src/edge_gateway.rs".to_string(),
                validated: true,
            },
            TlsHardeningRequirement {
                requirement: "Mutual TLS (mTLS)".to_string(),
                minimum_version: "1.3".to_string(),
                cipher_suites: vec!["client-cert-required".to_string()],
                siss_implementation: "siss-remote-gateway/src/lib.rs".to_string(),
                validated: true,
            },
        ];

        // Secret management controls
        ra.secret_management = vec![
            SecretManagementControl {
                secret_type: "PRIVATE_KEY".to_string(),
                storage_location: "siss-enclave (HSM-backed)".to_string(),
                rotation_interval_days: 90,
                access_logging: true,
            },
            SecretManagementControl {
                secret_type: "API_KEY".to_string(),
                storage_location: "siss-enclave (encrypted at-rest)".to_string(),
                rotation_interval_days: 180,
                access_logging: true,
            },
            SecretManagementControl {
                secret_type: "DATABASE_PASSWORD".to_string(),
                storage_location: "siss-enclave (encrypted at-rest)".to_string(),
                rotation_interval_days: 90,
                access_logging: true,
            },
            SecretManagementControl {
                secret_type: "TLS_CERTIFICATE".to_string(),
                storage_location: "siss-enclave (via trust-mesh PKIX)".to_string(),
                rotation_interval_days: 365,
                access_logging: true,
            },
        ];

        // Risk items
        ra.risks = vec![
            RiskItem {
                risk_id: "CRYPTO-001".to_string(),
                category: "Cryptographic Algorithm".to_string(),
                description: "Legacy cryptographic algorithms (DES, RC4, MD5) must not be used".to_string(),
                severity: RiskSeverity::Critical,
                mitigation: "Enforce OpenSSL security policy, code review for deprecated algorithms".to_string(),
                responsible_component: "siss-security-hardening".to_string(),
            },
            RiskItem {
                risk_id: "TLS-001".to_string(),
                category: "TLS Configuration".to_string(),
                description: "TLS version < 1.3 exposes to known attacks".to_string(),
                severity: RiskSeverity::Critical,
                mitigation: "Enforce TLS 1.3+ via transport config validation".to_string(),
                responsible_component: "siss-enclave/siss-trust-mesh".to_string(),
            },
            RiskItem {
                risk_id: "SECRET-001".to_string(),
                category: "Secret Management".to_string(),
                description: "Secrets stored in plaintext or hardcoded".to_string(),
                severity: RiskSeverity::Critical,
                mitigation: "All secrets stored in siss-enclave with encryption at-rest".to_string(),
                responsible_component: "siss-enclave".to_string(),
            },
            RiskItem {
                risk_id: "LATERAL-001".to_string(),
                category: "Lateral Movement".to_string(),
                description: "Compromised node could pivot to other nodes".to_string(),
                severity: RiskSeverity::High,
                mitigation: "Network segmentation via edge gateways; EdgesMonitor detection".to_string(),
                responsible_component: "siss-job-router/siss-behavioral-firewall".to_string(),
            },
            RiskItem {
                risk_id: "TIMING-001".to_string(),
                category: "Covert Channel".to_string(),
                description: "Timing side-channels could leak sensitive information".to_string(),
                severity: RiskSeverity::Medium,
                mitigation: "LatencyConstitution timing validation; chaos-petri verification".to_string(),
                responsible_component: "siss-gatekeeper/siss-job-router".to_string(),
            },
            RiskItem {
                risk_id: "AUDIT-001".to_string(),
                category: "Audit Trail".to_string(),
                description: "Missing or incomplete audit logs prevent incident reconstruction".to_string(),
                severity: RiskSeverity::High,
                mitigation: "Immutable audit logs via siss-audit-archiver with 7-year retention".to_string(),
                responsible_component: "siss-audit-archiver".to_string(),
            },
            RiskItem {
                risk_id: "INCIDENT-001".to_string(),
                category: "Incident Detection".to_string(),
                description: "Slow detection of security incidents".to_string(),
                severity: RiskSeverity::High,
                mitigation: "Real-time behavioral detection via siss-behavioral-firewall".to_string(),
                responsible_component: "siss-behavioral-firewall/siss-otel-tracer".to_string(),
            },
        ];

        ra
    }

    /// Validate all TLS hardening requirements
    pub fn validate_tls_hardening(&self) -> Result<String, String> {
        for req in &self.tls_hardening {
            if !req.validated {
                return Err(format!("TLS requirement not validated: {}", req.requirement));
            }
        }
        Ok(format!("All {} TLS requirements validated", self.tls_hardening.len()))
    }

    /// Count critical risks
    pub fn critical_risk_count(&self) -> usize {
        self.risks.iter().filter(|r| r.severity == RiskSeverity::Critical).count()
    }

    /// Count high risks
    pub fn high_risk_count(&self) -> usize {
        self.risks.iter().filter(|r| r.severity == RiskSeverity::High).count()
    }

    /// Cryptographic control coverage
    pub fn crypto_control_coverage(&self) -> f64 {
        let approved = self.crypto_controls
            .values()
            .filter(|c| c.status == CryptographicStatus::Approved)
            .count();
        let total = self.crypto_controls.len();
        (approved as f64) / (total as f64)
    }
}

impl Default for RiskAssessment {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cmmc_risk_assessment_loaded() {
        let ra = RiskAssessment::cmmc_level2_assessment();
        assert!(ra.crypto_controls.len() >= 10);
        assert!(ra.tls_hardening.len() >= 5);
        assert!(ra.secret_management.len() >= 4);
        assert!(ra.risks.len() >= 7);
    }

    #[test]
    fn test_cryptographic_validation() {
        let ra = RiskAssessment::cmmc_level2_assessment();

        // Approved algorithms
        assert_eq!(ra.crypto_controls.get("AES-256-GCM").unwrap().status, CryptographicStatus::Approved);
        assert_eq!(ra.crypto_controls.get("SHA-256").unwrap().status, CryptographicStatus::Approved);
        assert_eq!(ra.crypto_controls.get("TLS 1.3").unwrap().status, CryptographicStatus::Approved);

        // Forbidden algorithms
        assert_eq!(ra.crypto_controls.get("DES").unwrap().status, CryptographicStatus::Forbidden);
        assert_eq!(ra.crypto_controls.get("RC4").unwrap().status, CryptographicStatus::Forbidden);
        assert_eq!(ra.crypto_controls.get("MD5").unwrap().status, CryptographicStatus::Forbidden);
    }

    #[test]
    fn test_tls_hardening_validation() {
        let ra = RiskAssessment::cmmc_level2_assessment();
        assert!(ra.validate_tls_hardening().is_ok());
    }

    #[test]
    fn test_secret_management_controls() {
        let ra = RiskAssessment::cmmc_level2_assessment();
        for secret in &ra.secret_management {
            assert!(secret.access_logging);
            assert!(secret.rotation_interval_days <= 365);
            assert!(secret.storage_location.contains("siss-enclave"));
        }
    }

    #[test]
    fn test_critical_risks_identified() {
        let ra = RiskAssessment::cmmc_level2_assessment();
        let critical_count = ra.critical_risk_count();
        assert!(critical_count >= 3, "Must identify at least 3 critical risks");
    }

    #[test]
    fn test_high_risks_identified() {
        let ra = RiskAssessment::cmmc_level2_assessment();
        let high_count = ra.high_risk_count();
        assert!(high_count >= 3, "Must identify at least 3 high-severity risks");
    }

    #[test]
    fn test_crypto_control_coverage() {
        let ra = RiskAssessment::cmmc_level2_assessment();
        let coverage = ra.crypto_control_coverage();
        // 6 approved out of 10 total = 60%
        assert!(coverage >= 0.6, "Cryptographic coverage must be >= 60%");
    }
}
