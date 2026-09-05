use crate::country_deny::CountryDenyList;
use crate::ear::EarCategory;
use crate::itar::ItarCategory;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ClassificationLevel {
    Unclassified,
    CUI,
    Secret,
    TopSecret,
    TopSecretSCI,
}

#[derive(Debug, Clone)]
pub struct DefenseExportControl {
    pub classification: ClassificationLevel,
    pub itar_category: Option<ItarCategory>,
    pub ear_category: Option<EarCategory>,
    pub country_check: CountryDenyList,
    pub destination: Option<String>,
    pub export_control_passed: bool,
}

impl DefenseExportControl {
    pub fn new(classification: ClassificationLevel) -> Self {
        Self {
            classification,
            itar_category: None,
            ear_category: None,
            country_check: CountryDenyList::default(),
            destination: None,
            export_control_passed: false,
        }
    }

    pub fn check_country(&self, dest: &str) -> Result<(), String> {
        if self.country_check.is_denied(dest) {
            return Err(format!(
                "Export denied: destination '{}' is embargoed",
                dest
            ));
        }
        Ok(())
    }

    pub fn check_itar(&self) -> Result<(), String> {
        if self.itar_category.is_some() && self.classification != ClassificationLevel::Unclassified
        {
            return Err(
                "ITAR controlled item requires export license for classified technology"
                    .to_string(),
            );
        }
        Ok(())
    }

    pub fn check_ear(&self) -> Result<(), String> {
        if self.ear_category.is_some()
            && matches!(
                self.classification,
                ClassificationLevel::Secret
                    | ClassificationLevel::TopSecret
                    | ClassificationLevel::TopSecretSCI
            )
        {
            return Err(
                "EAR controlled item at Secret or above requires explicit EAR license".to_string(),
            );
        }
        Ok(())
    }

    pub fn validate_export(&self) -> Result<(), String> {
        if let Some(dest) = &self.destination {
            self.check_country(dest)?;
        }
        self.check_itar()?;
        self.check_ear()?;
        Ok(())
    }
}
