#[cfg(test)]
mod stream8_itar_ear {
    use crate::{
        ClassificationLevel, CountryDenyList, DefenseExportControl, EarCategory, ItarCategory,
    };

    #[test]
    fn test_ear_category_defined() {
        let cats = [
            EarCategory::Cat0,
            EarCategory::Cat1,
            EarCategory::Cat2,
            EarCategory::Cat3,
            EarCategory::Cat4,
            EarCategory::Cat5,
            EarCategory::Cat6,
            EarCategory::Cat7,
            EarCategory::Cat8,
            EarCategory::Cat9,
        ];
        assert_eq!(cats.len(), 10);
    }

    #[test]
    fn test_itar_category_defined() {
        let cats = [
            ItarCategory::I,
            ItarCategory::II,
            ItarCategory::III,
            ItarCategory::IV,
            ItarCategory::V,
            ItarCategory::VI,
            ItarCategory::VII,
            ItarCategory::VIII,
            ItarCategory::IX,
            ItarCategory::X,
            ItarCategory::XI,
            ItarCategory::XII,
            ItarCategory::XIII,
            ItarCategory::XIV,
            ItarCategory::XV,
            ItarCategory::XVI,
            ItarCategory::XVII,
            ItarCategory::XVIII,
            ItarCategory::XIX,
            ItarCategory::XX,
            ItarCategory::XXI,
        ];
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

#[cfg(test)]
mod stream8_dcma_filing {
    use crate::generate_dcma_package;

    #[test]
    fn test_dcma_filing_israel_no_blockers() {
        let result = generate_dcma_package("IL");
        assert!(result.is_ok());
        let pkg = result.unwrap();
        assert_eq!(pkg.destination, "IL");
        assert_eq!(pkg.eccn, "ECCN 5D002.c.1");
        assert!(pkg.filing_ready);
        assert!(!pkg.itar_controlled);
    }

    #[test]
    fn test_dcma_filing_iran_blocked() {
        let result = generate_dcma_package("IR");
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "COUNTRY_BLOCKED");
    }

    #[test]
    fn test_dcma_filing_germany_no_blockers() {
        let result = generate_dcma_package("DE");
        assert!(result.is_ok());
        let pkg = result.unwrap();
        assert_eq!(pkg.destination, "DE");
        assert!(pkg.filing_ready);
    }

    #[test]
    fn test_dcma_filing_north_korea_blocked() {
        let result = generate_dcma_package("KP");
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "COUNTRY_BLOCKED");
    }
}
