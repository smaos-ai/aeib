use siss_gatekeeper::sneakernet_ingress::SneakernetGateway;
/// Wave 1: Sneakernet Ingress Ritual & Chaos Petri Quarantine Zone
/// External model weights and Skill Packs must pass four fail-closed rules to enter the facility.
use uuid::Uuid;

/// Compile-time facility admission policy. Cannot be modified at runtime.
pub struct FacilityBounds {
    pub allowed_jurisdictions: &'static [&'static str],
    pub forbidden_origins: &'static [&'static str],
    pub max_artifact_bytes: u64,
    pub requires_sovereign_attestation: bool,
}

/// Manifest of an artifact seeking entry via sneakernet ingress.
#[derive(Debug, Clone)]
pub struct SneakernetManifest {
    pub artifact_id: Uuid,
    pub origin_jurisdiction: String,
    pub hash_sha256: String,
    pub size_bytes: u64,
    pub has_sovereign_attestation: bool,
}

/// Result of the admission ritual.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QuarantineVerdict {
    pub artifact_id: Uuid,
    pub approved: bool,
    pub reason: String,
}

/// Rejection reason from the four-rule closed set.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IngressRejection {
    ForbiddenOrigin { origin: String },
    OversizedArtifact { size: u64, cap: u64 },
    MissingAttestation,
    JurisdictionNotAllowed { jurisdiction: String },
}

pub struct FullIngressPipeline;

pub enum IngressRejection2 {
    JurisdictionFailed,
    GatewayFailed(String),
}

impl FullIngressPipeline {
    /// Run the complete ingress pipeline: IngressRitual → SneakernetGateway authorization
    pub fn run(
        manifest: &SneakernetManifest,
        bounds: &FacilityBounds,
        transfer_id: Uuid,
        gateway: &mut SneakernetGateway,
    ) -> Result<QuarantineVerdict, IngressRejection> {
        // Step 1: Run IngressRitual (jurisdiction/size/attestation checks)
        let verdict = IngressRitual::admit(manifest, bounds)?;

        // Step 2: Call gateway.authorize_transfer
        gateway
            .authorize_transfer(transfer_id)
            .map_err(|_| IngressRejection::MissingAttestation)?;

        Ok(verdict)
    }
}

pub struct IngressRitual;

impl IngressRitual {
    /// Chaos Petri quarantine: all four rules must pass.
    /// RULE A: origin not in forbidden_origins
    /// RULE B: origin_jurisdiction in allowed_jurisdictions
    /// RULE C: size_bytes <= max_artifact_bytes
    /// RULE D: if requires_sovereign_attestation → has_sovereign_attestation must be true
    pub fn admit(
        manifest: &SneakernetManifest,
        bounds: &FacilityBounds,
    ) -> Result<QuarantineVerdict, IngressRejection> {
        // RULE A: forbidden origins ban
        if bounds
            .forbidden_origins
            .iter()
            .any(|f| f == &manifest.origin_jurisdiction)
        {
            return Err(IngressRejection::ForbiddenOrigin {
                origin: manifest.origin_jurisdiction.clone(),
            });
        }

        // RULE B: jurisdiction allowlist
        if !bounds
            .allowed_jurisdictions
            .iter()
            .any(|a| a == &manifest.origin_jurisdiction)
        {
            return Err(IngressRejection::JurisdictionNotAllowed {
                jurisdiction: manifest.origin_jurisdiction.clone(),
            });
        }

        // RULE C: artifact size cap
        if manifest.size_bytes > bounds.max_artifact_bytes {
            return Err(IngressRejection::OversizedArtifact {
                size: manifest.size_bytes,
                cap: bounds.max_artifact_bytes,
            });
        }

        // RULE D: attestation requirement
        if bounds.requires_sovereign_attestation && !manifest.has_sovereign_attestation {
            return Err(IngressRejection::MissingAttestation);
        }

        Ok(QuarantineVerdict {
            artifact_id: manifest.artifact_id,
            approved: true,
            reason: "all_rules_passed".to_string(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_admit_valid_il_with_attestation() {
        let bounds = FacilityBounds {
            allowed_jurisdictions: &["IL", "EU"],
            forbidden_origins: &["CN", "UNVERIFIED"],
            max_artifact_bytes: 10 * 1024 * 1024 * 1024,
            requires_sovereign_attestation: true,
        };

        let manifest = SneakernetManifest {
            artifact_id: Uuid::new_v4(),
            origin_jurisdiction: "IL".to_string(),
            hash_sha256: "a".repeat(64),
            size_bytes: 1024 * 1024,
            has_sovereign_attestation: true,
        };

        let result = IngressRitual::admit(&manifest, &bounds);
        assert!(result.is_ok());
        assert!(result.unwrap().approved);
    }

    #[test]
    fn test_reject_forbidden_origin() {
        let bounds = FacilityBounds {
            allowed_jurisdictions: &["IL"],
            forbidden_origins: &["CN"],
            max_artifact_bytes: 10 * 1024 * 1024 * 1024,
            requires_sovereign_attestation: true,
        };

        let manifest = SneakernetManifest {
            artifact_id: Uuid::new_v4(),
            origin_jurisdiction: "CN".to_string(),
            hash_sha256: "a".repeat(64),
            size_bytes: 1024,
            has_sovereign_attestation: true,
        };

        let result = IngressRitual::admit(&manifest, &bounds);
        assert!(matches!(
            result,
            Err(IngressRejection::ForbiddenOrigin { .. })
        ));
    }

    #[test]
    fn test_reject_oversized_artifact() {
        let bounds = FacilityBounds {
            allowed_jurisdictions: &["IL"],
            forbidden_origins: &[],
            max_artifact_bytes: 1024 * 1024,
            requires_sovereign_attestation: false,
        };

        let manifest = SneakernetManifest {
            artifact_id: Uuid::new_v4(),
            origin_jurisdiction: "IL".to_string(),
            hash_sha256: "a".repeat(64),
            size_bytes: 10 * 1024 * 1024,
            has_sovereign_attestation: false,
        };

        let result = IngressRitual::admit(&manifest, &bounds);
        assert!(matches!(
            result,
            Err(IngressRejection::OversizedArtifact { .. })
        ));
    }

    #[test]
    fn test_reject_missing_attestation() {
        let bounds = FacilityBounds {
            allowed_jurisdictions: &["IL"],
            forbidden_origins: &[],
            max_artifact_bytes: 10 * 1024 * 1024 * 1024,
            requires_sovereign_attestation: true,
        };

        let manifest = SneakernetManifest {
            artifact_id: Uuid::new_v4(),
            origin_jurisdiction: "IL".to_string(),
            hash_sha256: "a".repeat(64),
            size_bytes: 1024,
            has_sovereign_attestation: false,
        };

        let result = IngressRitual::admit(&manifest, &bounds);
        assert!(matches!(result, Err(IngressRejection::MissingAttestation)));
    }
}
