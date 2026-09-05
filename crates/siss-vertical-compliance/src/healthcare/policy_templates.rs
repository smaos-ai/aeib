use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Healthcare-specific ReBAC roles aligned to HIPAA Privacy/Security Rules
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HealthcareRole {
    /// Chief Privacy Officer, full control over data governance and breach response
    PrivacyOfficer,
    /// Clinical staff, can access patient PHI for treatment purposes
    ClinicalStaff,
    /// Data analyst, can access aggregated/de-identified data only
    DataAnalyst,
    /// Auditor, can review access logs but cannot modify
    ComplianceAuditor,
}

/// Healthcare-specific attributes for AP2 evaluation (HIPAA context)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthcareAttributes {
    pub access_scope: String, // "Own Patients", "Department", "Entire Facility"
    pub phi_sensitivity: String, // "Public Health Data", "Clinical Notes", "Mental Health", "HIV/AIDS"
    pub purpose_of_access: String, // "Treatment", "Payment", "Operations", "Research"
    pub minimum_necessary: bool, // HIPAA Minimum Necessary Standard
    pub encryption_key_controlled: bool, // Customer controls encryption key (required)
}

/// HIPAA-specific audit context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HIPAAuditContext {
    pub requester_id: Uuid,
    pub requester_role: HealthcareRole,
    pub action: String,
    pub phi_elements_accessed: Vec<String>, // ["Name", "DOB", "Medical Record #"]
    pub patient_ids_accessed: usize,
    pub purpose: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Generates a HIPAA-compliant role template
pub fn healthcare_role_template(role: HealthcareRole) -> RoleTemplate {
    match role {
        HealthcareRole::PrivacyOfficer => RoleTemplate {
            name: "HIPAA Privacy Officer".to_string(),
            can_access_phi: true,
            phi_scope: "All".to_string(),
            can_approve_data_access: true,
            can_initiate_breach_response: true,
            audit_log_access: true,
            mfa_required: true,
            maximum_access_duration_hours: 24,
            dua_required: true,
        },
        HealthcareRole::ClinicalStaff => RoleTemplate {
            name: "Clinical Staff".to_string(),
            can_access_phi: true,
            phi_scope: "Patient-Assigned".to_string(),
            can_approve_data_access: false,
            can_initiate_breach_response: false,
            audit_log_access: false,
            mfa_required: true,
            maximum_access_duration_hours: 8,
            dua_required: true,
        },
        HealthcareRole::DataAnalyst => RoleTemplate {
            name: "Data Analyst".to_string(),
            can_access_phi: false, // Only de-identified data
            phi_scope: "Aggregated/De-identified".to_string(),
            can_approve_data_access: false,
            can_initiate_breach_response: false,
            audit_log_access: false,
            mfa_required: false,
            maximum_access_duration_hours: 12,
            dua_required: false, // De-identified data exempt from HIPAA
        },
        HealthcareRole::ComplianceAuditor => RoleTemplate {
            name: "HIPAA Compliance Auditor".to_string(),
            can_access_phi: false, // Logs only
            phi_scope: "Audit Logs Only".to_string(),
            can_approve_data_access: false,
            can_initiate_breach_response: false,
            audit_log_access: true,
            mfa_required: true,
            maximum_access_duration_hours: 24,
            dua_required: false,
        },
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoleTemplate {
    pub name: String,
    pub can_access_phi: bool,
    pub phi_scope: String,
    pub can_approve_data_access: bool,
    pub can_initiate_breach_response: bool,
    pub audit_log_access: bool,
    pub mfa_required: bool,
    pub maximum_access_duration_hours: u32,
    pub dua_required: bool,
}

/// HIPAA Minimum Necessary Standard: return only data needed for stated purpose
pub fn enforce_minimum_necessary(
    requested_fields: Vec<&str>,
    purpose: &str,
) -> Result<Vec<String>, String> {
    // Define minimum necessary field sets per HIPAA purpose
    let minimum_fields = match purpose {
        "Treatment" => {
            vec!["PatientID", "MedicalHistory", "CurrentMedications", "Allergies", "DiagnosisCodes"]
        }
        "Payment" => vec!["PatientID", "InsuranceInfo", "DiagnosisCodes", "ProcedureCodes"],
        "Operations" => vec!["PatientID", "Admission Date", "Facility Location"],
        "Research" => vec!["Age", "Gender", "DiagnosisCodes"], // De-identified
        _ => return Err("Unknown purpose".to_string()),
    };

    let allowed_fields: Vec<String> = requested_fields
        .iter()
        .filter(|f| minimum_fields.contains(f))
        .map(|f| f.to_string())
        .collect();

    if allowed_fields.is_empty() {
        return Err(format!(
            "No requested fields meet Minimum Necessary Standard for purpose: {}",
            purpose
        ));
    }

    Ok(allowed_fields)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_privacy_officer_has_full_access() {
        let role = healthcare_role_template(HealthcareRole::PrivacyOfficer);
        assert!(role.can_access_phi);
        assert_eq!(role.phi_scope, "All");
        assert!(role.can_initiate_breach_response);
    }

    #[test]
    fn test_clinical_staff_has_patient_assigned_access() {
        let role = healthcare_role_template(HealthcareRole::ClinicalStaff);
        assert!(role.can_access_phi);
        assert_eq!(role.phi_scope, "Patient-Assigned");
        assert!(!role.can_approve_data_access);
    }

    #[test]
    fn test_data_analyst_cannot_access_phi() {
        let role = healthcare_role_template(HealthcareRole::DataAnalyst);
        assert!(!role.can_access_phi);
        assert!(!role.dua_required);
    }

    #[test]
    fn test_minimum_necessary_for_treatment() {
        let fields = vec!["PatientID", "MedicalHistory", "SocialSecurityNumber"];
        let result = enforce_minimum_necessary(fields, "Treatment");
        assert!(result.is_ok());
        let allowed = result.unwrap();
        assert!(allowed.contains(&"PatientID".to_string()));
        assert!(!allowed.contains(&"SocialSecurityNumber".to_string())); // Not minimum necessary
    }

    #[test]
    fn test_minimum_necessary_denies_excessive_fields() {
        let fields = vec!["SocialSecurityNumber", "BankAccount"];
        let result = enforce_minimum_necessary(fields, "Treatment");
        assert!(result.is_err());
    }
}
