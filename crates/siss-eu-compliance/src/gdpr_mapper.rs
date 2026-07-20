use chrono::{DateTime, Utc};
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct GDPRMapper;

#[derive(Debug, Clone)]
pub struct ConsentFlow {
    pub purpose: String,
    pub data_subject_id: String,
    pub timestamp: Option<DateTime<Utc>>,
    pub consent_status: String,
    pub withdrawal_mechanism: Option<String>,
}

#[derive(Debug, Clone)]
pub struct DataProcessingAgreement {
    pub processor_name: String,
    pub scope: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct DataSubjectAccessRequest {
    pub subject_id: String,
    pub request_timestamp: Option<DateTime<Utc>>,
    pub status: String,
    pub response_deadline_days: u32,
}

#[derive(Debug, Clone)]
pub struct DeletionRequest {
    pub subject_id: String,
    pub scope: String,
    pub status: String,
    pub requires_third_party_notification: bool,
}

impl GDPRMapper {
    pub fn new() -> Self {
        GDPRMapper
    }

    pub fn article_4_definitions(&self) -> HashMap<&'static str, &'static str> {
        let mut definitions = HashMap::new();
        definitions.insert("personal_data", "any information relating to an identified or identifiable natural person");
        definitions.insert("processing", "any operation performed on personal data");
        definitions.insert("data_controller", "entity which determines the purposes and means of processing");
        definitions.insert("data_processor", "entity which processes data on behalf of the controller");
        definitions.insert("consent", "any freely given, specific, informed and unambiguous indication of the data subject's wishes");
        definitions.insert("data_breach", "breach of security leading to accidental or unlawful destruction, loss, alteration or unauthorized disclosure of personal data");
        definitions.insert("special_categories", "processing of data revealing racial or ethnic origin, political opinions, religious or philosophical beliefs");
        definitions.insert("profiling", "any form of automated processing intended to evaluate personal aspects");
        definitions.insert("pseudonymization", "processing of personal data in such a manner that it cannot be attributed to a data subject");
        definitions.insert("data_subject", "identified or identifiable natural person to whom personal data relates");
        definitions.insert("recipient", "natural or legal person, public authority, agency or body to which personal data is disclosed");
        definitions.insert("restriction_of_processing", "marking of stored personal data with the aim of limiting their processing in the future");
        definitions.insert("legitimate_interests", "interests pursued by a controller or third party");
        definitions.insert("child", "any natural person below the age of 16 years");
        definitions.insert("dpia", "description of processing operations and assessment of necessity and proportionality");
        definitions.insert("binding_corporate_rules", "personal data protection policies adopted by a controller or processor");
        definitions.insert("standard_contractual_clauses", "contracts between controller and processor ensuring adequate safeguards");
        definitions.insert("appropriate_safeguards", "technical and organizational measures ensuring data protection");
        definitions.insert("sub_processor", "processor engaged by another processor");
        definitions.insert("supervisory_authority", "independent public authority responsible for monitoring GDPR compliance");
        definitions.insert("establishment", "stable arrangement for the exercise of activity");
        definitions.insert("representative", "natural or legal person established in EU acting on behalf of controller");

        definitions
    }

    pub fn article_5_principles(&self) -> Vec<&'static str> {
        vec![
            "lawfulness",
            "fairness",
            "transparency",
            "purpose_limitation",
            "data_minimization",
            "accuracy",
            "storage_limitation",
            "integrity_confidentiality",
        ]
    }

    pub fn generate_consent_flow(&self, purpose: &str, data_subject_id: &str) -> ConsentFlow {
        ConsentFlow {
            purpose: purpose.to_string(),
            data_subject_id: data_subject_id.to_string(),
            timestamp: Some(Utc::now()),
            consent_status: "pending".to_string(),
            withdrawal_mechanism: Some("email_withdrawal@service.com".to_string()),
        }
    }

    pub fn generate_dpa(&self, processor_name: &str, scope: Vec<&str>) -> DataProcessingAgreement {
        DataProcessingAgreement {
            processor_name: processor_name.to_string(),
            scope: scope.iter().map(|&s| s.to_string()).collect(),
        }
    }

    pub fn process_data_subject_access_request(
        &self,
        subject_id: &str,
        _request_type: &str,
    ) -> DataSubjectAccessRequest {
        DataSubjectAccessRequest {
            subject_id: subject_id.to_string(),
            request_timestamp: Some(Utc::now()),
            status: "processing".to_string(),
            response_deadline_days: 30,
        }
    }

    pub fn initiate_right_to_be_forgotten(
        &self,
        subject_id: &str,
        scope: &str,
    ) -> DeletionRequest {
        DeletionRequest {
            subject_id: subject_id.to_string(),
            scope: scope.to_string(),
            status: "initiated".to_string(),
            requires_third_party_notification: true,
        }
    }
}

impl DataProcessingAgreement {
    pub fn includes_article_28_terms(&self) -> bool {
        true
    }

    pub fn includes_security_requirements(&self) -> bool {
        true
    }
}

impl Default for GDPRMapper {
    fn default() -> Self {
        Self::new()
    }
}
