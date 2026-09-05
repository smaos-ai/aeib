use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Language {
    ZhCn,  // Chinese (Simplified)
    JaJp,  // Japanese
    KoKr,  // Korean
    ThTh,  // Thai
    ViVn,  // Vietnamese
    IdId,  // Indonesian
    PtBr,  // Portuguese (Brazil)
    EsMx,  // Spanish (Mexico)
    TaIn,  // Tamil (India)
    HiIn,  // Hindi (India)
    BnIn,  // Bengali (India)
    FilPh, // Filipino (Philippines)
    MyMm,  // Burmese (Myanmar)
    KmKh,  // Khmer (Cambodia)
}

impl Language {
    pub fn code(&self) -> &'static str {
        match self {
            Language::ZhCn => "zh_CN",
            Language::JaJp => "ja_JP",
            Language::KoKr => "ko_KR",
            Language::ThTh => "th_TH",
            Language::ViVn => "vi_VN",
            Language::IdId => "id_ID",
            Language::PtBr => "pt_BR",
            Language::EsMx => "es_MX",
            Language::TaIn => "ta_IN",
            Language::HiIn => "hi_IN",
            Language::BnIn => "bn_IN",
            Language::FilPh => "fil_PH",
            Language::MyMm => "my_MM",
            Language::KmKh => "km_KH",
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            Language::ZhCn => "Chinese (Simplified)",
            Language::JaJp => "Japanese",
            Language::KoKr => "Korean",
            Language::ThTh => "Thai",
            Language::ViVn => "Vietnamese",
            Language::IdId => "Indonesian",
            Language::PtBr => "Portuguese (Brazil)",
            Language::EsMx => "Spanish (Mexico)",
            Language::TaIn => "Tamil",
            Language::HiIn => "Hindi",
            Language::BnIn => "Bengali",
            Language::FilPh => "Filipino",
            Language::MyMm => "Burmese",
            Language::KmKh => "Khmer",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranslationKey {
    pub key: String,
    pub translations: HashMap<String, String>,
}

pub struct Localizer {
    strings: HashMap<String, HashMap<String, String>>,
}

impl Localizer {
    pub fn new() -> Self {
        Localizer {
            strings: HashMap::new(),
        }
    }

    pub fn add_translation(&mut self, key: &str, lang: Language, value: String) {
        self.strings
            .entry(key.to_string())
            .or_default()
            .insert(lang.code().to_string(), value);
    }

    pub fn get(&self, key: &str, lang: Language) -> Option<String> {
        self.strings
            .get(key)
            .and_then(|translations| translations.get(lang.code()).cloned())
    }

    pub fn translate(&self, key: &str, lang: Language) -> crate::Result<String> {
        self.get(key, lang).ok_or_else(|| {
            crate::ApacError::LocalizationError(format!(
                "Translation not found: {} for language {}",
                key,
                lang.code()
            ))
        })
    }

    pub fn supported_languages() -> Vec<Language> {
        vec![
            Language::ZhCn,
            Language::JaJp,
            Language::KoKr,
            Language::ThTh,
            Language::ViVn,
            Language::IdId,
            Language::PtBr,
            Language::EsMx,
            Language::TaIn,
            Language::HiIn,
            Language::BnIn,
            Language::FilPh,
            Language::MyMm,
            Language::KmKh,
        ]
    }

    pub fn coverage(&self) -> f64 {
        if self.strings.is_empty() {
            return 0.0;
        }

        let total_langs = Self::supported_languages().len();
        let coverage: f64 = self
            .strings
            .values()
            .map(|translations| translations.len() as f64 / total_langs as f64)
            .sum();

        coverage / self.strings.len() as f64
    }
}

impl Default for Localizer {
    fn default() -> Self {
        Self::new()
    }
}
