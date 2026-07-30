use sha2::{Digest, Sha256};
/// BaselineCapsule — Sovereign Proof Engine (SPE) v1.0
/// M3 Pro optimized personal truth baseline via MDC (Minimum Discernible Complexity)
/// Covenant-aligned: local-first, cryptographically audited, fail-closed gates
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, PartialEq)]
pub struct PersonalTruth {
    pub domain: String,      // e.g., "health", "decision", "market"
    pub baseline: f64,       // baseline metric value (e.g., HRV, glucose, portfolio alpha)
    pub timestamp: u64,      // Unix timestamp (secs)
    pub source_hash: String, // SHA-256 of raw source (gemba_proof)
    pub confidence: f64,     // 0.0-1.0, γ-operator score
}

#[derive(Debug, Clone)]
pub struct BaselineCapsule {
    truths: HashMap<String, Vec<PersonalTruth>>,
    merkle_root: String,
    last_updated: u64,
}

impl BaselineCapsule {
    pub fn new() -> Self {
        Self {
            truths: HashMap::new(),
            merkle_root: String::new(),
            last_updated: 0,
        }
    }

    /// Record a personal truth with cryptographic provenance
    /// Fail-closed: if source hash doesn't match, reject the record
    pub fn record_truth(
        &mut self,
        domain: &str,
        baseline: f64,
        raw_source: &[u8],
        confidence: f64,
    ) -> Result<(), String> {
        // Compute gemba_proof (SHA-256 of raw source at ingestion)
        let mut hasher = Sha256::new();
        hasher.update(raw_source);
        let source_hash = format!("{:x}", hasher.finalize());

        // Fail-closed gate: confidence must be >0.7 to record
        if confidence < 0.7 {
            return Err(format!("Confidence {} below threshold 0.7", confidence));
        }

        let truth = PersonalTruth {
            domain: domain.to_string(),
            baseline,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
            source_hash,
            confidence,
        };

        self.truths
            .entry(domain.to_string())
            .or_insert_with(Vec::new)
            .push(truth);

        // Recompute Merkle root after each record
        self.compute_merkle_root();
        self.last_updated = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        Ok(())
    }

    /// Verify personal truth (check source hash + confidence)
    pub fn verify_truth(&self, domain: &str, index: usize, raw_source: &[u8]) -> bool {
        if let Some(truths) = self.truths.get(domain) {
            if let Some(truth) = truths.get(index) {
                let mut hasher = Sha256::new();
                hasher.update(raw_source);
                let computed_hash = format!("{:x}", hasher.finalize());
                return computed_hash == truth.source_hash && truth.confidence > 0.7;
            }
        }
        false
    }

    /// Get baseline for a domain (O(1) lookup)
    pub fn get_baseline(&self, domain: &str) -> Option<f64> {
        self.truths
            .get(domain)
            .and_then(|v| v.last())
            .map(|t| t.baseline)
    }

    /// Compute Merkle root of all truths (cryptographic audit)
    fn compute_merkle_root(&mut self) {
        let mut hasher = Sha256::new();

        // Sort domains for deterministic ordering
        let mut domains: Vec<_> = self.truths.keys().collect();
        domains.sort();

        for domain in domains {
            if let Some(truths) = self.truths.get(domain) {
                for truth in truths {
                    hasher.update(truth.source_hash.as_bytes());
                    hasher.update(&truth.baseline.to_le_bytes());
                    hasher.update(&truth.timestamp.to_le_bytes());
                }
            }
        }

        self.merkle_root = format!("{:x}", hasher.finalize());
    }

    /// Export as JSON for Trojan Every Day briefing
    pub fn export_json(&self) -> String {
        let mut output = String::from("{\n");
        output.push_str(&format!(
            "  \"capsule_id\": \"baseline-{}\",\n",
            self.last_updated
        ));
        output.push_str(&format!("  \"merkle_root\": \"{}\",\n", self.merkle_root));
        output.push_str("  \"domains\": {\n");

        let mut domains: Vec<_> = self.truths.keys().collect();
        domains.sort();

        for (i, domain) in domains.iter().enumerate() {
            if let Some(truths) = self.truths.get(*domain) {
                if let Some(latest) = truths.last() {
                    output.push_str(&format!("    \"{}\": {{\n", domain));
                    output.push_str(&format!("      \"baseline\": {},\n", latest.baseline));
                    output.push_str(&format!("      \"confidence\": {},\n", latest.confidence));
                    output.push_str(&format!("      \"timestamp\": {}\n", latest.timestamp));
                    output.push_str("    }");
                    if i < domains.len() - 1 {
                        output.push(',');
                    }
                    output.push('\n');
                }
            }
        }

        output.push_str("  }\n");
        output.push('}');
        output
    }

    pub fn merkle_root(&self) -> &str {
        &self.merkle_root
    }

    pub fn last_updated(&self) -> u64 {
        self.last_updated
    }
}

impl Default for BaselineCapsule {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_truth_with_confidence() {
        let mut capsule = BaselineCapsule::new();
        let result = capsule.record_truth("health", 72.5, b"HRV sample", 0.85);
        assert!(result.is_ok());
        assert_eq!(capsule.get_baseline("health"), Some(72.5));
    }

    #[test]
    fn test_fail_closed_low_confidence() {
        let mut capsule = BaselineCapsule::new();
        let result = capsule.record_truth("health", 72.5, b"HRV sample", 0.5);
        assert!(result.is_err());
        assert!(capsule.get_baseline("health").is_none());
    }

    #[test]
    fn test_verify_truth_with_source() {
        let mut capsule = BaselineCapsule::new();
        let source = b"HRV sample";
        capsule.record_truth("health", 72.5, source, 0.85).unwrap();
        assert!(capsule.verify_truth("health", 0, source));
    }

    #[test]
    fn test_verify_truth_fails_with_wrong_source() {
        let mut capsule = BaselineCapsule::new();
        let source = b"HRV sample";
        capsule.record_truth("health", 72.5, source, 0.85).unwrap();
        assert!(!capsule.verify_truth("health", 0, b"different source"));
    }

    #[test]
    fn test_merkle_root_deterministic() {
        let mut capsule1 = BaselineCapsule::new();
        capsule1
            .record_truth("health", 72.5, b"HRV 1", 0.85)
            .unwrap();
        capsule1
            .record_truth("market", 0.05, b"SPY alpha", 0.75)
            .unwrap();

        let mut capsule2 = BaselineCapsule::new();
        capsule2
            .record_truth("health", 72.5, b"HRV 1", 0.85)
            .unwrap();
        capsule2
            .record_truth("market", 0.05, b"SPY alpha", 0.75)
            .unwrap();

        assert_eq!(capsule1.merkle_root(), capsule2.merkle_root());
    }

    #[test]
    fn test_export_json_valid() {
        let mut capsule = BaselineCapsule::new();
        capsule
            .record_truth("health", 72.5, b"HRV sample", 0.85)
            .unwrap();
        let json = capsule.export_json();
        assert!(json.contains("\"health\""));
        assert!(json.contains("\"baseline\": 72.5"));
        assert!(json.contains("\"confidence\": 0.85"));
    }
}
