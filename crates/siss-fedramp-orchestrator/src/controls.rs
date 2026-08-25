use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ControlFamily {
    AccessControl,
    AuditAndAccountability,
    IdentificationAndAuthentication,
    SystemAndCommunicationsProtection,
    SystemAndInformationIntegrity,
    IncidentResponse,
    ContingencyPlanning,
    ConfigurationManagement,
    RiskAssessment,
    PlanningAndManagement,
}

impl ControlFamily {
    pub fn code(&self) -> &'static str {
        match self {
            ControlFamily::AccessControl => "AC",
            ControlFamily::AuditAndAccountability => "AU",
            ControlFamily::IdentificationAndAuthentication => "IA",
            ControlFamily::SystemAndCommunicationsProtection => "SC",
            ControlFamily::SystemAndInformationIntegrity => "SI",
            ControlFamily::IncidentResponse => "IR",
            ControlFamily::ContingencyPlanning => "CP",
            ControlFamily::ConfigurationManagement => "CM",
            ControlFamily::RiskAssessment => "RA",
            ControlFamily::PlanningAndManagement => "PM",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FedRAMPControl {
    pub id: String,
    pub family: ControlFamily,
    pub title: String,
    pub description: String,
}

impl FedRAMPControl {
    pub fn new(id: &str, family: ControlFamily, title: &str, description: &str) -> Self {
        Self {
            id: id.to_string(),
            family,
            title: title.to_string(),
            description: description.to_string(),
        }
    }
}
