use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CriticalAssetType {
    Cryptography,
    IncidentResponse,
    SupplyChain,
    Authentication,
    AccessControl,
    AuditLogging,
}

impl CriticalAssetType {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Cryptography => "cryptography",
            Self::IncidentResponse => "incident_response",
            Self::SupplyChain => "supply_chain",
            Self::Authentication => "authentication",
            Self::AccessControl => "access_control",
            Self::AuditLogging => "audit_logging",
        }
    }
}

#[derive(Debug, Clone)]
pub struct CriticalAsset {
    pub asset_id: String,
    pub asset_type: CriticalAssetType,
    pub component: String,
    pub description: String,
}

/// Maps SISS components to NIS2 critical asset categories
pub struct NIS2AssetMapper {
    assets: HashMap<CriticalAssetType, Vec<CriticalAsset>>,
}

impl NIS2AssetMapper {
    pub fn new() -> Self {
        let mut assets: HashMap<CriticalAssetType, Vec<CriticalAsset>> = HashMap::new();

        // Cryptography assets
        assets.insert(
            CriticalAssetType::Cryptography,
            vec![
                CriticalAsset {
                    asset_id: "crypto-001".to_string(),
                    asset_type: CriticalAssetType::Cryptography,
                    component: "siss-behavioral-firewall".to_string(),
                    description: "AES-256 encryption for rule compliance".to_string(),
                },
                CriticalAsset {
                    asset_id: "crypto-002".to_string(),
                    asset_type: CriticalAssetType::Cryptography,
                    component: "siss-gatekeeper".to_string(),
                    description: "RSA-4096 key management for access policies".to_string(),
                },
                CriticalAsset {
                    asset_id: "crypto-003".to_string(),
                    asset_type: CriticalAssetType::Cryptography,
                    component: "siss-graph-db".to_string(),
                    description: "SHA-256 hash verification for graph integrity".to_string(),
                },
            ],
        );

        // Incident Response assets
        assets.insert(
            CriticalAssetType::IncidentResponse,
            vec![
                CriticalAsset {
                    asset_id: "incident-001".to_string(),
                    asset_type: CriticalAssetType::IncidentResponse,
                    component: "siss-feedback-router".to_string(),
                    description: "Incident detection and escalation mechanism".to_string(),
                },
                CriticalAsset {
                    asset_id: "incident-002".to_string(),
                    asset_type: CriticalAssetType::IncidentResponse,
                    component: "siss-agent-shell".to_string(),
                    description: "Emergency shutdown and containment protocols".to_string(),
                },
                CriticalAsset {
                    asset_id: "incident-003".to_string(),
                    asset_type: CriticalAssetType::IncidentResponse,
                    component: "siss-gdpr-nis2".to_string(),
                    description: "Security event logging and breach notification".to_string(),
                },
            ],
        );

        // Supply Chain assets
        assets.insert(
            CriticalAssetType::SupplyChain,
            vec![
                CriticalAsset {
                    asset_id: "supply-001".to_string(),
                    asset_type: CriticalAssetType::SupplyChain,
                    component: "siss-agent-card".to_string(),
                    description: "Agent identity and capability provenance".to_string(),
                },
                CriticalAsset {
                    asset_id: "supply-002".to_string(),
                    asset_type: CriticalAssetType::SupplyChain,
                    component: "siss-context-cartography".to_string(),
                    description: "Dependency mapping and trust boundaries".to_string(),
                },
                CriticalAsset {
                    asset_id: "supply-003".to_string(),
                    asset_type: CriticalAssetType::SupplyChain,
                    component: "siss-job-router".to_string(),
                    description: "Task routing and execution provenance".to_string(),
                },
            ],
        );

        // Authentication assets
        assets.insert(
            CriticalAssetType::Authentication,
            vec![
                CriticalAsset {
                    asset_id: "auth-001".to_string(),
                    asset_type: CriticalAssetType::Authentication,
                    component: "siss-gatekeeper".to_string(),
                    description: "Multi-factor authentication enforcement".to_string(),
                },
                CriticalAsset {
                    asset_id: "auth-002".to_string(),
                    asset_type: CriticalAssetType::Authentication,
                    component: "siss-agent-shell".to_string(),
                    description: "Agent credential validation".to_string(),
                },
            ],
        );

        // Access Control assets
        assets.insert(
            CriticalAssetType::AccessControl,
            vec![
                CriticalAsset {
                    asset_id: "ac-001".to_string(),
                    asset_type: CriticalAssetType::AccessControl,
                    component: "siss-gatekeeper".to_string(),
                    description: "Role-based access control (RBAC)".to_string(),
                },
                CriticalAsset {
                    asset_id: "ac-002".to_string(),
                    asset_type: CriticalAssetType::AccessControl,
                    component: "siss-behavioral-firewall".to_string(),
                    description: "Behavioral anomaly detection for access".to_string(),
                },
            ],
        );

        // Audit Logging assets
        assets.insert(
            CriticalAssetType::AuditLogging,
            vec![
                CriticalAsset {
                    asset_id: "audit-001".to_string(),
                    asset_type: CriticalAssetType::AuditLogging,
                    component: "siss-gdpr-nis2".to_string(),
                    description: "Immutable security audit trail (merkle-tree)".to_string(),
                },
                CriticalAsset {
                    asset_id: "audit-002".to_string(),
                    asset_type: CriticalAssetType::AuditLogging,
                    component: "siss-graph-db".to_string(),
                    description: "Data access and modification logs".to_string(),
                },
            ],
        );

        Self { assets }
    }

    /// Retrieves critical assets by type
    pub fn get_assets_by_type(&self, asset_type: CriticalAssetType) -> Vec<CriticalAsset> {
        self.assets.get(&asset_type).cloned().unwrap_or_default()
    }

    /// Retrieves all assets across all types
    pub fn get_all_assets(&self) -> Vec<CriticalAsset> {
        self.assets
            .values()
            .flat_map(|assets| assets.iter().cloned())
            .collect()
    }

    /// Gets NIS2 readiness score (0-100) based on asset coverage
    pub fn calculate_readiness_score(&self) -> f64 {
        let total_assets = self.get_all_assets().len() as f64;
        let min_required_assets = 12.0; // Minimum assets per critical category

        if total_assets >= min_required_assets {
            100.0
        } else {
            (total_assets / min_required_assets) * 100.0
        }
    }
}

impl Default for NIS2AssetMapper {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mapper_has_all_asset_types() {
        let mapper = NIS2AssetMapper::new();
        assert!(!mapper
            .get_assets_by_type(CriticalAssetType::Cryptography)
            .is_empty());
        assert!(!mapper
            .get_assets_by_type(CriticalAssetType::IncidentResponse)
            .is_empty());
        assert!(!mapper
            .get_assets_by_type(CriticalAssetType::SupplyChain)
            .is_empty());
        assert!(!mapper
            .get_assets_by_type(CriticalAssetType::Authentication)
            .is_empty());
        assert!(!mapper
            .get_assets_by_type(CriticalAssetType::AccessControl)
            .is_empty());
        assert!(!mapper
            .get_assets_by_type(CriticalAssetType::AuditLogging)
            .is_empty());
    }

    #[test]
    fn test_readiness_score_calculated() {
        let mapper = NIS2AssetMapper::new();
        let score = mapper.calculate_readiness_score();
        assert!(score > 0.0 && score <= 100.0);
    }
}
