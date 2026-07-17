use std::collections::HashSet;

/// Validates that data is strictly stored in EU regions (Frankfurt primary)
pub struct EUDataGuard {
    allowed_domains: HashSet<String>,
}

impl EUDataGuard {
    pub fn new() -> Self {
        let mut allowed = HashSet::new();
        // EU-GDPR compliant storage domains
        allowed.insert("eu-central-1.amazonaws.com".to_string()); // AWS Frankfurt
        allowed.insert("eu-west-1.amazonaws.com".to_string());    // AWS Ireland
        allowed.insert("eu-north-1.amazonaws.com".to_string());   // AWS Stockholm
        allowed.insert("europe-west1.gcp.com".to_string());       // GCP Brussels
        allowed.insert("europe-west4.gcp.com".to_string());       // GCP Netherlands
        allowed.insert("eu-de.cloud.ibm.com".to_string());        // IBM Frankfurt
        allowed.insert("local-frankfurt".to_string());             // On-premise Frankfurt

        Self { allowed_domains: allowed }
    }

    /// Validates that a domain/email belongs to EU residency
    pub fn validate_frankfurt_residency(&self, domain_or_email: &str) -> Result<(), String> {
        // Extract domain from email if applicable
        let domain = if domain_or_email.contains('@') {
            let parts: Vec<&str> = domain_or_email.split('@').collect();
            if parts.len() == 2 {
                parts[1]
            } else {
                domain_or_email
            }
        } else {
            domain_or_email
        };

        if self.is_eu_domain(domain) {
            Ok(())
        } else {
            Err(format!("Non-EU domain detected: {}. Data must reside in Frankfurt region.", domain))
        }
    }

    fn is_eu_domain(&self, domain: &str) -> bool {
        self.allowed_domains.iter().any(|allowed| domain.contains(allowed))
    }
}

impl Default for EUDataGuard {
    fn default() -> Self {
        Self::new()
    }
}

/// Validates EU domain compliance (top-level domain check)
pub struct DomainValidator {
    eu_tlds: HashSet<String>,
}

impl DomainValidator {
    pub fn new() -> Self {
        let mut tlds = HashSet::new();
        // EU country TLDs
        for tld in &[
            "de", "fr", "it", "es", "nl", "be", "at", "ch", "se", "dk", "no", "fi",
            "pl", "cz", "ie", "pt", "gr", "hu", "ro", "bg", "hr", "si", "sk", "lt",
            "lv", "ee", "cy", "lu", "mt", "eu" // EU generic TLD
        ] {
            tlds.insert(tld.to_string());
        }
        Self { eu_tlds: tlds }
    }

    /// Validates if a domain is an EU domain
    pub fn is_eu_domain(&self, domain: &str) -> Result<(), String> {
        let parts: Vec<&str> = domain.split('.').collect();
        if parts.len() < 2 {
            return Err(format!("Invalid domain format: {}", domain));
        }

        let tld = parts[parts.len() - 1];
        if self.eu_tlds.contains(tld) {
            Ok(())
        } else {
            Err(format!("Non-EU TLD detected: .{}. Data residency requires EU domains.", tld))
        }
    }
}

impl Default for DomainValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_eu_data_guard_accepts_aws_frankfurt() {
        let guard = EUDataGuard::new();
        assert!(guard.validate_frankfurt_residency("eu-central-1.amazonaws.com").is_ok());
    }

    #[test]
    fn test_eu_data_guard_rejects_us_domain() {
        let guard = EUDataGuard::new();
        assert!(guard.validate_frankfurt_residency("us-east-1.amazonaws.com").is_err());
    }

    #[test]
    fn test_domain_validator_accepts_de() {
        let validator = DomainValidator::new();
        assert!(validator.is_eu_domain("example.de").is_ok());
    }

    #[test]
    fn test_domain_validator_rejects_com() {
        let validator = DomainValidator::new();
        assert!(validator.is_eu_domain("example.com").is_err());
    }

    #[test]
    fn test_domain_validator_accepts_eu_generic() {
        let validator = DomainValidator::new();
        assert!(validator.is_eu_domain("example.eu").is_ok());
    }
}
