#[cfg(test)]
mod stream8_itar_ear {
    use crate::{ClassificationLevel, CountryDenyList, DefenseExportControl, EarCategory, ItarCategory};

    #[test]
    fn test_ear_category_defined() {
        let cats = [EarCategory::Cat0, EarCategory::Cat1, EarCategory::Cat2, EarCategory::Cat3,
                    EarCategory::Cat4, EarCategory::Cat5, EarCategory::Cat6, EarCategory::Cat7,
                    EarCategory::Cat8, EarCategory::Cat9];
        assert_eq!(cats.len(), 10);
    }

    #[test]
    fn test_itar_category_defined() {
        let cats = [ItarCategory::I, ItarCategory::II, ItarCategory::III, ItarCategory::IV,
                    ItarCategory::V, ItarCategory::VI, ItarCategory::VII, ItarCategory::VIII,
                    ItarCategory::IX, ItarCategory::X, ItarCategory::XI, ItarCategory::XII,
                    ItarCategory::XIII, ItarCategory::XIV, ItarCategory::XV, ItarCategory::XVI,
                    ItarCategory::XVII, ItarCategory::XVIII, ItarCategory::XIX, ItarCategory::XX,
                    ItarCategory::XXI];
        assert_eq!(cats.len(), 21);
    }

    #[test]
    fn test_country_deny_list_has_ofac_defaults() {
        let list = CountryDenyList::seed_ofac();
        assert!(list.embargoed.len() >= 6);
    }

    #[test]
    fn test_country_deny_rejects_iran() {
        let list = CountryDenyList::seed_ofac();
        assert!(list.is_denied("IR"));
    }

    #[test]
    fn test_country_deny_allows_germany() {
        let list = CountryDenyList::seed_ofac();
        assert!(!list.is_denied("DE"));
    }

    #[test]
    fn test_export_control_sequential_checks() {
        let mut ctrl = DefenseExportControl::new(ClassificationLevel::Unclassified);
        ctrl.country_check = CountryDenyList::seed_ofac();
        ctrl.destination = Some("IR".to_string());
        let result = ctrl.validate_export();
        assert!(result.is_err());
    }

    #[test]
    fn test_export_control_all_pass() {
        let mut ctrl = DefenseExportControl::new(ClassificationLevel::Unclassified);
        ctrl.country_check = CountryDenyList::seed_ofac();
        ctrl.destination = Some("DE".to_string());
        let result = ctrl.validate_export();
        assert!(result.is_ok());
    }
}
