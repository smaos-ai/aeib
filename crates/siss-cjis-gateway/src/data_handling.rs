use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SensitivityLevel {
    Public,
    Internal,
    Confidential,
    CJISRestricted,
}

impl SensitivityLevel {
    pub fn requires_encryption(&self) -> bool {
        matches!(self, SensitivityLevel::Confidential | SensitivityLevel::CJISRestricted)
    }

    pub fn requires_audit_log(&self) -> bool {
        matches!(self, SensitivityLevel::Confidential | SensitivityLevel::CJISRestricted)
    }

    pub fn minimum_classification(&self) -> &str {
        match self {
            SensitivityLevel::Public => "Public",
            SensitivityLevel::Internal => "Internal",
            SensitivityLevel::Confidential => "Confidential",
            SensitivityLevel::CJISRestricted => "Restricted",
        }
    }
}

#[derive(Debug, Clone)]
pub struct DataHandler {
    sensitivity_level: SensitivityLevel,
}

impl DataHandler {
    pub fn new(sensitivity_level: SensitivityLevel) -> Self {
        Self { sensitivity_level }
    }

    pub fn requires_criminal_justice_safeguards(&self) -> bool {
        self.sensitivity_level == SensitivityLevel::CJISRestricted
    }

    pub fn enforces_need_to_know(&self) -> bool {
        matches!(
            self.sensitivity_level,
            SensitivityLevel::Confidential | SensitivityLevel::CJISRestricted
        )
    }

    pub fn supports_biometric_data_protection(&self) -> bool {
        self.sensitivity_level == SensitivityLevel::CJISRestricted
    }

    pub fn enforces_biometric_encryption(&self) -> bool {
        self.sensitivity_level == SensitivityLevel::CJISRestricted
    }

    pub fn sensitivity_level(&self) -> SensitivityLevel {
        self.sensitivity_level
    }
}
