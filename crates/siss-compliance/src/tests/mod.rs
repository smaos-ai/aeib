#[cfg(test)]
mod stream7_regulatory_mappers {
    use crate::{
        basel3::BaselIiiMapper,
        hipaa::HipaaSecurityMapper,
        nist::{NistControlEvidence, NistControlFamily, NistControlMapper},
    };

    #[test]
    fn test_nist_20_families_defined() {
        let families = [
            NistControlFamily::AC,
            NistControlFamily::AT,
            NistControlFamily::AU,
            NistControlFamily::CA,
            NistControlFamily::CM,
            NistControlFamily::CP,
            NistControlFamily::IA,
            NistControlFamily::IR,
            NistControlFamily::MA,
            NistControlFamily::MP,
            NistControlFamily::PE,
            NistControlFamily::PL,
            NistControlFamily::PM,
            NistControlFamily::PS,
            NistControlFamily::PT,
            NistControlFamily::RA,
            NistControlFamily::SA,
            NistControlFamily::SC,
            NistControlFamily::SI,
            NistControlFamily::SR,
        ];
        assert_eq!(families.len(), 20);
    }

    #[test]
    fn test_nist_seed_populates_20_controls() {
        let mapper = NistControlMapper::seed_from_axiom();
        assert_eq!(mapper.len(), 20);
    }

    #[test]
    fn test_nist_score_percentage_calc() {
        let mut mapper = NistControlMapper::new();
        for i in 0..18_usize {
            mapper.insert(
                format!("AC-{}", i),
                NistControlEvidence {
                    standard_ref: format!("NIST SP 800-53 Rev5 AC-{}", i),
                    implementation_ref: "src/policy.rs".to_string(),
                },
            );
        }
        let score = mapper.score();
        assert!(
            (score - 0.9_f64).abs() < 1e-9,
            "expected 0.9, got {}",
            score
        );
    }

    #[test]
    fn test_hipaa_18_required_controls() {
        assert_eq!(HipaaSecurityMapper::required_controls(), 18);
    }

    #[test]
    fn test_basel_capital_ratio_8_percent() {
        let mapper = BaselIiiMapper::new();
        let ratio = mapper
            .capital_adequacy_ratio(1_000_000_000, 80_000_000)
            .unwrap();
        assert!((ratio - 0.08).abs() < 1e-9, "expected 0.08, got {}", ratio);
        assert!(mapper.meets_minimum_capital(1_000_000_000, 80_000_000));
    }

    #[test]
    fn test_basel_capital_below_minimum() {
        let mapper = BaselIiiMapper::new();
        let ratio = mapper
            .capital_adequacy_ratio(1_000_000_000, 50_000_000)
            .unwrap();
        assert!((ratio - 0.05).abs() < 1e-9, "expected 0.05, got {}", ratio);
        assert!(!mapper.meets_minimum_capital(1_000_000_000, 50_000_000));
    }

    #[test]
    fn test_hipaa_missing_required_drops_score() {
        let mut mapper = HipaaSecurityMapper::new();
        for i in 0..9_usize {
            mapper.insert(
                format!("HIPAA-{}", i),
                crate::hipaa::HipaaControlEvidence {
                    section_ref: format!("§164.312({i})"),
                    implementation_ref: "siss-enclave/src/lib.rs".to_string(),
                },
            );
        }
        let score = mapper.score();
        assert!((score - 0.5).abs() < 1e-9, "expected 0.5, got {}", score);
    }
}
