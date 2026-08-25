use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Defense-specific ReBAC roles aligned to FedRAMP
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DefenseRole {
    /// Full control, can authorize other users, access all classification levels
    SecurityOfficer,
    /// Access to Secret/SCI, can audit decisions, cannot approve
    Auditor,
    /// Access to Unclassified only, read-only governance reports
    Analyst,
    /// System-level operations (deploy, maintain)
    SystemAdministrator,
}

/// Defense-specific attributes for AP2 evaluation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DefenseAttributes {
    pub clearance_level: String, // "Unclassified", "Secret", "TopSecret", "SCI"
    pub facility_tier: String,   // "T1" (best security), "T2", "T3"
    pub program_authorization: Vec<String>, // ["Project X", "Operation Y"]
    pub country_authorized: Vec<String>, // ["US", "CA", "UK", "AU"]
    pub is_us_citizen: bool,
}

/// FedRAMP-specific audit context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FedRAMPAuditContext {
    pub requester_id: Uuid,
    pub requester_role: DefenseRole,
    pub action: String,
    pub classification_level: String,
    pub facility: String,
    pub authorization_source: String, // "DCID 6/4", "Executive Order", "NIST SP 800-53"
}

/// Generates a FedRAMP-compliant role template
pub fn defense_role_template(role: DefenseRole) -> RoleTemplate {
    match role {
        DefenseRole::SecurityOfficer => RoleTemplate {
            name: "FedRAMP Security Officer".to_string(),
            can_access_classifications: vec!["Unclassified", "Secret", "TopSecret", "SCI"]
                .iter()
                .map(|s| s.to_string())
                .collect(),
            can_approve_actions: vec!["policy_change", "facility_access", "data_export"]
                .iter()
                .map(|s| s.to_string())
                .collect(),
            audit_log_access: true,
            can_delegate: true,
            max_delegation_depth: 2,
            mfa_required: true,
            facility_tiers: vec!["T1", "T2", "T3"].iter().map(|s| s.to_string()).collect(),
        },
        DefenseRole::Auditor => RoleTemplate {
            name: "FedRAMP Auditor".to_string(),
            can_access_classifications: vec!["Unclassified", "Secret", "SCI"]
                .iter()
                .map(|s| s.to_string())
                .collect(),
            can_approve_actions: vec![], // Read-only
            audit_log_access: true,
            can_delegate: false,
            max_delegation_depth: 0,
            mfa_required: true,
            facility_tiers: vec!["T1", "T2"].iter().map(|s| s.to_string()).collect(),
        },
        DefenseRole::Analyst => RoleTemplate {
            name: "FedRAMP Analyst".to_string(),
            can_access_classifications: vec!["Unclassified"]
                .iter()
                .map(|s| s.to_string())
                .collect(),
            can_approve_actions: vec![],
            audit_log_access: false,
            can_delegate: false,
            max_delegation_depth: 0,
            mfa_required: false,
            facility_tiers: vec!["T3"].iter().map(|s| s.to_string()).collect(),
        },
        DefenseRole::SystemAdministrator => RoleTemplate {
            name: "FedRAMP System Administrator".to_string(),
            can_access_classifications: vec!["Unclassified", "Secret", "TopSecret"]
                .iter()
                .map(|s| s.to_string())
                .collect(),
            can_approve_actions: vec!["system_deploy", "configuration_change", "user_provision"]
                .iter()
                .map(|s| s.to_string())
                .collect(),
            audit_log_access: true,
            can_delegate: false,
            max_delegation_depth: 0,
            mfa_required: true,
            facility_tiers: vec!["T1", "T2", "T3"].iter().map(|s| s.to_string()).collect(),
        },
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoleTemplate {
    pub name: String,
    pub can_access_classifications: Vec<String>,
    pub can_approve_actions: Vec<String>,
    pub audit_log_access: bool,
    pub can_delegate: bool,
    pub max_delegation_depth: u8,
    pub mfa_required: bool,
    pub facility_tiers: Vec<String>,
}

/// Export control check for FedRAMP: block re-export to non-authorized countries
pub fn check_export_control(
    destination_country: &str,
    classification: &str,
) -> Result<(), String> {
    let allowed_countries = vec!["US", "CA", "UK", "AU", "NZ", "DE", "NL", "BE", "FR"];

    if !allowed_countries.contains(&destination_country) {
        return Err(format!(
            "Export of {} to {} blocked by FedRAMP export control",
            classification, destination_country
        ));
    }

    // Top Secret cannot leave US
    if classification == "TopSecret" && destination_country != "US" {
        return Err("Top Secret classification cannot be exported".to_string());
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_security_officer_role_has_full_access() {
        let role = defense_role_template(DefenseRole::SecurityOfficer);
        assert!(role.can_delegate);
        assert_eq!(role.can_access_classifications.len(), 4);
        assert!(role.audit_log_access);
    }

    #[test]
    fn test_analyst_role_has_limited_access() {
        let role = defense_role_template(DefenseRole::Analyst);
        assert!(!role.can_delegate);
        assert_eq!(role.can_access_classifications.len(), 1);
        assert!(!role.audit_log_access);
    }

    #[test]
    fn test_export_control_blocks_non_allies() {
        let result = check_export_control("CN", "Unclassified");
        assert!(result.is_err());
    }

    #[test]
    fn test_export_control_allows_five_eyes() {
        let result = check_export_control("UK", "Unclassified");
        assert!(result.is_ok());
    }

    #[test]
    fn test_export_control_blocks_topsecret_export() {
        let result = check_export_control("UK", "TopSecret");
        assert!(result.is_err());
    }
}
