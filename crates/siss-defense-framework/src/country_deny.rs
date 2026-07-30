#[derive(Debug, Clone)]
pub struct CountryDenyList {
    pub embargoed: Vec<String>,
}

impl CountryDenyList {
    pub fn is_denied(&self, country_code: &str) -> bool {
        self.embargoed
            .iter()
            .any(|c| c.eq_ignore_ascii_case(country_code))
    }

    pub fn seed_ofac() -> Self {
        Self {
            embargoed: vec![
                "IR".to_string(),
                "KP".to_string(),
                "SY".to_string(),
                "CU".to_string(),
                "RU".to_string(),
                "BY".to_string(),
                "VE".to_string(),
                "MM".to_string(),
            ],
        }
    }
}

impl Default for CountryDenyList {
    fn default() -> Self {
        Self {
            embargoed: Vec::new(),
        }
    }
}
