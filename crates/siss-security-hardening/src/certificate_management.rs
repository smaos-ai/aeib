use chrono::{DateTime, Duration, Utc};
use rand::Rng;
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum CertificateError {
    #[error("Certificate expired")]
    CertificateExpired,
    #[error("Invalid certificate: {0}")]
    InvalidCertificate(String),
    #[error("Certificate not found")]
    CertificateNotFound,
    #[error("Hostname mismatch in certificate")]
    HostnameMismatch,
    #[error("Certificate generation failed: {0}")]
    GenerationFailed(String),
}

/// X.509 Certificate representation
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Certificate {
    pub subject: String, // CN (Common Name)
    pub issuer: String,  // Certificate issuer
    pub not_before: DateTime<Utc>,
    pub not_after: DateTime<Utc>,
    pub serial_number: String,
    pub public_key: Vec<u8>,
    pub signature: Vec<u8>,
    pub extensions: Vec<String>, // SAN (Subject Alternative Names)
}

impl Certificate {
    /// Check if certificate is still valid
    pub fn is_valid(&self) -> Result<(), CertificateError> {
        let now = Utc::now();

        if now < self.not_before {
            return Err(CertificateError::InvalidCertificate(
                "Certificate not yet valid".to_string(),
            ));
        }

        if now > self.not_after {
            return Err(CertificateError::CertificateExpired);
        }

        Ok(())
    }

    /// Check if certificate matches the given hostname
    pub fn matches_hostname(&self, hostname: &str) -> Result<(), CertificateError> {
        if self.subject.contains(hostname) {
            return Ok(());
        }

        if self.extensions.iter().any(|ext| ext.contains(hostname)) {
            return Ok(());
        }

        Err(CertificateError::HostnameMismatch)
    }

    /// Get days until expiration
    pub fn days_until_expiration(&self) -> i64 {
        let duration = self.not_after - Utc::now();
        duration.num_days()
    }
}

/// TLS Configuration with certificate pinning
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TLSConfig {
    pub tls_version: String,              // "1.3" or "1.2"
    pub enable_mtls: bool,                // Mutual TLS
    pub certificate_pinning: bool,        // Certificate pinning enabled
    pub pinned_certificates: Vec<String>, // SHA256 hashes of pinned certs
    pub cipher_suites: Vec<String>,       // Allowed cipher suites
}

impl TLSConfig {
    /// Create a secure TLS 1.3 config with mTLS
    pub fn tls_13_with_mtls() -> Self {
        Self {
            tls_version: "1.3".to_string(),
            enable_mtls: true,
            certificate_pinning: true,
            pinned_certificates: Vec::new(),
            cipher_suites: vec![
                "TLS_AES_256_GCM_SHA384".to_string(),
                "TLS_CHACHA20_POLY1305_SHA256".to_string(),
            ],
        }
    }

    /// Validate TLS configuration
    pub fn validate(&self) -> Result<(), CertificateError> {
        match self.tls_version.as_str() {
            "1.2" | "1.3" => Ok(()),
            _ => Err(CertificateError::InvalidCertificate(
                "Invalid TLS version".to_string(),
            )),
        }
    }
}

impl Default for TLSConfig {
    fn default() -> Self {
        Self::tls_13_with_mtls()
    }
}

/// Certificate manager for issuing and validating certificates
pub struct CertificateManager {
    issued_certificates: std::sync::Mutex<Vec<Certificate>>,
    trusted_cas: Vec<String>, // Trusted CA certificates (base64)
    tls_config: TLSConfig,
}

impl CertificateManager {
    pub fn new(tls_config: TLSConfig) -> Result<Self, CertificateError> {
        tls_config.validate()?;

        Ok(Self {
            issued_certificates: std::sync::Mutex::new(Vec::new()),
            trusted_cas: Vec::new(),
            tls_config,
        })
    }

    /// Generate a self-signed certificate for testing
    pub fn generate_self_signed(
        &self,
        subject: &str,
        days_valid: i32,
    ) -> Result<Certificate, CertificateError> {
        let now = Utc::now();
        let not_after = now + Duration::days(days_valid as i64);

        // Generate a random public key (in real implementation, use RSA/ECDSA)
        let mut public_key = [0u8; 32];
        rand::thread_rng().fill(&mut public_key);

        let serial = format!("{}", uuid::Uuid::new_v4());

        Ok(Certificate {
            subject: subject.to_string(),
            issuer: "SovereignNexus-CA".to_string(),
            not_before: now,
            not_after,
            serial_number: serial,
            public_key: public_key.to_vec(),
            signature: vec![0u8; 64], // Placeholder
            extensions: vec![format!("DNS:{}", subject)],
        })
    }

    /// Store a certificate
    pub fn store_certificate(&self, cert: Certificate) -> Result<(), CertificateError> {
        cert.is_valid()?;

        let mut certs = self
            .issued_certificates
            .lock()
            .map_err(|e| CertificateError::InvalidCertificate(e.to_string()))?;
        certs.push(cert);

        Ok(())
    }

    /// Get a certificate by subject
    pub fn get_certificate(&self, subject: &str) -> Result<Certificate, CertificateError> {
        let certs = self
            .issued_certificates
            .lock()
            .map_err(|e| CertificateError::InvalidCertificate(e.to_string()))?;

        certs
            .iter()
            .find(|c| c.subject == subject)
            .cloned()
            .ok_or(CertificateError::CertificateNotFound)
    }

    /// Validate a certificate for a specific use
    pub fn validate_certificate_for_hostname(
        &self,
        cert: &Certificate,
        hostname: &str,
    ) -> Result<(), CertificateError> {
        cert.is_valid()?;
        cert.matches_hostname(hostname)?;

        // Check certificate pinning if enabled
        if self.tls_config.certificate_pinning {
            let cert_hash = self.compute_certificate_hash(cert);
            if !self.tls_config.pinned_certificates.contains(&cert_hash) {
                return Err(CertificateError::InvalidCertificate(
                    "Certificate not pinned".to_string(),
                ));
            }
        }

        Ok(())
    }

    /// Compute SHA256 hash of certificate (for pinning)
    pub fn compute_certificate_hash(&self, cert: &Certificate) -> String {
        use sha2::{Digest, Sha256};

        let mut hasher = Sha256::new();
        hasher.update(cert.subject.as_bytes());
        hasher.update(cert.serial_number.as_bytes());
        hasher.update(&cert.public_key);

        format!("{:x}", hasher.finalize())
    }

    /// Add a certificate to the pinning list
    pub fn pin_certificate(&mut self, cert: &Certificate) {
        let hash = self.compute_certificate_hash(cert);
        if !self.tls_config.pinned_certificates.contains(&hash) {
            self.tls_config.pinned_certificates.push(hash);
        }
    }

    /// Check certificate expiration and warn if expiring soon
    pub fn check_expiration(&self, subject: &str) -> Result<i64, CertificateError> {
        let cert = self.get_certificate(subject)?;
        Ok(cert.days_until_expiration())
    }

    pub fn tls_config(&self) -> &TLSConfig {
        &self.tls_config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_certificate_validity() {
        let now = Utc::now();
        let cert = Certificate {
            subject: "test.sovereignnexus.com".to_string(),
            issuer: "CA".to_string(),
            not_before: now,
            not_after: now + Duration::days(365),
            serial_number: "12345".to_string(),
            public_key: vec![0u8; 32],
            signature: vec![0u8; 64],
            extensions: vec!["DNS:test.sovereignnexus.com".to_string()],
        };

        assert!(cert.is_valid().is_ok());
    }

    #[test]
    fn test_expired_certificate() {
        let now = Utc::now();
        let cert = Certificate {
            subject: "test.sovereignnexus.com".to_string(),
            issuer: "CA".to_string(),
            not_before: now - Duration::days(365),
            not_after: now - Duration::days(1),
            serial_number: "12345".to_string(),
            public_key: vec![0u8; 32],
            signature: vec![0u8; 64],
            extensions: vec![],
        };

        assert!(matches!(
            cert.is_valid(),
            Err(CertificateError::CertificateExpired)
        ));
    }

    #[test]
    fn test_hostname_matching() {
        let now = Utc::now();
        let cert = Certificate {
            subject: "CN=example.com".to_string(),
            issuer: "CA".to_string(),
            not_before: now,
            not_after: now + Duration::days(365),
            serial_number: "12345".to_string(),
            public_key: vec![0u8; 32],
            signature: vec![0u8; 64],
            extensions: vec![
                "DNS:example.com".to_string(),
                "DNS:www.example.com".to_string(),
            ],
        };

        assert!(cert.matches_hostname("example.com").is_ok());
        assert!(cert.matches_hostname("www.example.com").is_ok());
        assert!(cert.matches_hostname("other.com").is_err());
    }

    #[test]
    fn test_certificate_manager_generation() {
        let tls_config = TLSConfig::tls_13_with_mtls();
        let manager = CertificateManager::new(tls_config).expect("Create manager");

        let cert = manager
            .generate_self_signed("agent-01.sovereignnexus.com", 365)
            .expect("Generate cert");

        assert!(cert.is_valid().is_ok());
    }

    #[test]
    fn test_certificate_storage_and_retrieval() {
        let tls_config = TLSConfig::tls_13_with_mtls();
        let manager = CertificateManager::new(tls_config).expect("Create manager");

        let cert = manager
            .generate_self_signed("agent-01.sovereignnexus.com", 365)
            .expect("Generate cert");

        manager.store_certificate(cert.clone()).expect("Store cert");

        let retrieved = manager
            .get_certificate("agent-01.sovereignnexus.com")
            .expect("Retrieve cert");

        assert_eq!(retrieved.subject, cert.subject);
    }

    #[test]
    fn test_certificate_pinning() {
        let mut tls_config = TLSConfig::tls_13_with_mtls();
        tls_config.certificate_pinning = true;

        let mut manager = CertificateManager::new(tls_config).expect("Create manager");

        let cert = manager
            .generate_self_signed("pinned.sovereignnexus.com", 365)
            .expect("Generate cert");

        manager.pin_certificate(&cert);

        let result = manager.validate_certificate_for_hostname(&cert, "pinned.sovereignnexus.com");
        assert!(result.is_ok());
    }

    #[test]
    fn test_tls_config_validation() {
        let config = TLSConfig::tls_13_with_mtls();
        assert!(config.validate().is_ok());

        let invalid_config = TLSConfig {
            tls_version: "2.0".to_string(),
            ..Default::default()
        };
        assert!(invalid_config.validate().is_err());
    }

    #[test]
    fn test_days_until_expiration() {
        let now = Utc::now();
        let cert = Certificate {
            subject: "test.com".to_string(),
            issuer: "CA".to_string(),
            not_before: now,
            not_after: now + Duration::days(30),
            serial_number: "123".to_string(),
            public_key: vec![],
            signature: vec![],
            extensions: vec![],
        };

        let days = cert.days_until_expiration();
        assert!(days >= 29 && days <= 30);
    }
}
