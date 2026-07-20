#[cfg(test)]
mod tests {
    use crate::{Language, Localizer};

    #[test]
    fn test_chinese_simplified_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("hello", Language::ZhCn, "你好".to_string());

        let result = localizer.get("hello", Language::ZhCn);
        assert_eq!(result, Some("你好".to_string()));
    }

    #[test]
    fn test_japanese_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("welcome", Language::JaJp, "ようこそ".to_string());

        let result = localizer.get("welcome", Language::JaJp);
        assert_eq!(result, Some("ようこそ".to_string()));
    }

    #[test]
    fn test_korean_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("goodbye", Language::KoKr, "안녕히 가세요".to_string());

        let result = localizer.get("goodbye", Language::KoKr);
        assert_eq!(result, Some("안녕히 가세요".to_string()));
    }

    #[test]
    fn test_thai_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("thank_you", Language::ThTh, "ขอบคุณ".to_string());

        let result = localizer.get("thank_you", Language::ThTh);
        assert_eq!(result, Some("ขอบคุณ".to_string()));
    }

    #[test]
    fn test_vietnamese_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("yes", Language::ViVn, "Có".to_string());

        let result = localizer.get("yes", Language::ViVn);
        assert_eq!(result, Some("Có".to_string()));
    }

    #[test]
    fn test_indonesian_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("no", Language::IdId, "Tidak".to_string());

        let result = localizer.get("no", Language::IdId);
        assert_eq!(result, Some("Tidak".to_string()));
    }

    #[test]
    fn test_portuguese_brazil_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("ok", Language::PtBr, "Tudo bem".to_string());

        let result = localizer.get("ok", Language::PtBr);
        assert_eq!(result, Some("Tudo bem".to_string()));
    }

    #[test]
    fn test_spanish_mexico_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("hello", Language::EsMx, "Hola".to_string());

        let result = localizer.get("hello", Language::EsMx);
        assert_eq!(result, Some("Hola".to_string()));
    }

    #[test]
    fn test_language_code_mappings() {
        assert_eq!(Language::ZhCn.code(), "zh_CN");
        assert_eq!(Language::JaJp.code(), "ja_JP");
        assert_eq!(Language::KoKr.code(), "ko_KR");
        assert_eq!(Language::ThTh.code(), "th_TH");
        assert_eq!(Language::ViVn.code(), "vi_VN");
        assert_eq!(Language::IdId.code(), "id_ID");
        assert_eq!(Language::PtBr.code(), "pt_BR");
        assert_eq!(Language::EsMx.code(), "es_MX");
    }

    #[test]
    fn test_supported_languages_count() {
        let languages = Localizer::supported_languages();
        assert_eq!(languages.len(), 14);
    }

    #[test]
    fn test_translation_coverage_calculation() {
        let mut localizer = Localizer::new();
        localizer.add_translation("key1", Language::ZhCn, "value1".to_string());
        localizer.add_translation("key1", Language::JaJp, "value2".to_string());

        let coverage = localizer.coverage();
        assert!(coverage > 0.0 && coverage < 1.0);
    }

    #[test]
    fn test_missing_translation_error() {
        let localizer = Localizer::new();
        let result = localizer.translate("nonexistent", Language::ZhCn);
        assert!(result.is_err());
    }

    #[test]
    fn test_multilingual_same_key() {
        let mut localizer = Localizer::new();
        localizer.add_translation("greeting", Language::ZhCn, "你好".to_string());
        localizer.add_translation("greeting", Language::JaJp, "こんにちは".to_string());
        localizer.add_translation("greeting", Language::KoKr, "안녕하세요".to_string());

        assert_eq!(localizer.get("greeting", Language::ZhCn), Some("你好".to_string()));
        assert_eq!(localizer.get("greeting", Language::JaJp), Some("こんにちは".to_string()));
        assert_eq!(localizer.get("greeting", Language::KoKr), Some("안녕하세요".to_string()));
    }

    #[test]
    fn test_tamil_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("hi", Language::TaIn, "வணக்கம்".to_string());

        let result = localizer.get("hi", Language::TaIn);
        assert_eq!(result, Some("வணக்கம்".to_string()));
    }

    #[test]
    fn test_hindi_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("hello", Language::HiIn, "नमस्ते".to_string());

        let result = localizer.get("hello", Language::HiIn);
        assert_eq!(result, Some("नमस्ते".to_string()));
    }

    #[test]
    fn test_bengali_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("greet", Language::BnIn, "নমস্কার".to_string());

        let result = localizer.get("greet", Language::BnIn);
        assert_eq!(result, Some("নমস্কার".to_string()));
    }

    #[test]
    fn test_tagalog_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("hi", Language::FilPh, "Kamusta".to_string());

        let result = localizer.get("hi", Language::FilPh);
        assert_eq!(result, Some("Kamusta".to_string()));
    }

    #[test]
    fn test_burmese_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("hello", Language::MyMm, "မင်္ဂလာပါ".to_string());

        let result = localizer.get("hello", Language::MyMm);
        assert_eq!(result, Some("မင်္ဂလာပါ".to_string()));
    }

    #[test]
    fn test_khmer_localization() {
        let mut localizer = Localizer::new();
        localizer.add_translation("greeting", Language::KmKh, "សូស្វាគមន៍".to_string());

        let result = localizer.get("greeting", Language::KmKh);
        assert_eq!(result, Some("សូស្វាគមន៍".to_string()));
    }
}
