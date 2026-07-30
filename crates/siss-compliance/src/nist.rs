use std::collections::HashMap;

/// NIST SP 800-53 Rev 5 control families
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum NistControlFamily {
    AC, // Access Control
    AT, // Awareness and Training
    AU, // Audit and Accountability
    CA, // Assessment, Authorization, and Monitoring
    CM, // Configuration Management
    CP, // Contingency Planning
    IA, // Identification and Authentication
    IR, // Incident Response
    MA, // Maintenance
    MP, // Media Protection
    PE, // Physical and Environmental Protection
    PL, // Planning
    PM, // Program Management
    PS, // Personnel Security
    PT, // PII Processing and Transparency
    RA, // Risk Assessment
    SA, // System and Services Acquisition
    SC, // System and Communications Protection
    SI, // System and Information Integrity
    SR, // Supply Chain Risk Management
}

/// Evidence record linking a NIST control to its implementation
#[derive(Debug, Clone)]
pub struct NistControlEvidence {
    /// Reference to the NIST standard (e.g., "NIST SP 800-53 Rev5 AC-2")
    pub standard_ref: String,
    /// Reference to local implementation (e.g., "siss-gatekeeper/src/policy.rs")
    pub implementation_ref: String,
}

/// Maps NIST SP 800-53 controls to implementation evidence
pub struct NistControlMapper {
    controls: HashMap<String, NistControlEvidence>,
}

impl NistControlMapper {
    /// Creates an empty mapper
    pub fn new() -> Self {
        Self {
            controls: HashMap::new(),
        }
    }

    /// Pre-populates 20 controls spanning all NIST control families from SISS axioms
    pub fn seed_from_axiom() -> Self {
        let mut m = Self::new();
        let seeds: &[(&str, &str, &str)] = &[
            (
                "AC-2",
                "NIST SP 800-53 Rev5 AC-2",
                "siss-gatekeeper/src/policy.rs",
            ),
            (
                "AT-1",
                "NIST SP 800-53 Rev5 AT-1",
                "docs/training/awareness.md",
            ),
            (
                "AU-2",
                "NIST SP 800-53 Rev5 AU-2",
                "siss-audit-archiver/src/lib.rs",
            ),
            (
                "CA-7",
                "NIST SP 800-53 Rev5 CA-7",
                "siss-compliance/src/eu_ai_act.rs",
            ),
            (
                "CM-6",
                "NIST SP 800-53 Rev5 CM-6",
                "siss-os-sidecar/src/config.rs",
            ),
            (
                "CP-9",
                "NIST SP 800-53 Rev5 CP-9",
                "siss-decision-db/src/backup.rs",
            ),
            (
                "IA-2",
                "NIST SP 800-53 Rev5 IA-2",
                "siss-enclave/src/identity.rs",
            ),
            (
                "IR-4",
                "NIST SP 800-53 Rev5 IR-4",
                "siss-behavioral-firewall/src/lib.rs",
            ),
            (
                "MA-2",
                "NIST SP 800-53 Rev5 MA-2",
                "docs/ops/maintenance.md",
            ),
            (
                "MP-5",
                "NIST SP 800-53 Rev5 MP-5",
                "siss-enclave/src/media.rs",
            ),
            (
                "PE-3",
                "NIST SP 800-53 Rev5 PE-3",
                "docs/physical/access_control.md",
            ),
            (
                "PL-2",
                "NIST SP 800-53 Rev5 PL-2",
                "docs/architecture/security_plan.md",
            ),
            (
                "PM-1",
                "NIST SP 800-53 Rev5 PM-1",
                "docs/program/info_security.md",
            ),
            (
                "PS-3",
                "NIST SP 800-53 Rev5 PS-3",
                "docs/hr/personnel_screening.md",
            ),
            (
                "PT-2",
                "NIST SP 800-53 Rev5 PT-2",
                "siss-compliance/src/consent.rs",
            ),
            (
                "RA-5",
                "NIST SP 800-53 Rev5 RA-5",
                "siss-security-hardening/src/vuln_scan.rs",
            ),
            (
                "SA-11",
                "NIST SP 800-53 Rev5 SA-11",
                "docs/dev/code_review.md",
            ),
            (
                "SC-8",
                "NIST SP 800-53 Rev5 SC-8",
                "siss-enclave/src/tls.rs",
            ),
            (
                "SI-3",
                "NIST SP 800-53 Rev5 SI-3",
                "siss-behavioral-firewall/src/malware.rs",
            ),
            (
                "SR-3",
                "NIST SP 800-53 Rev5 SR-3",
                "docs/supply_chain/vendor_policy.md",
            ),
        ];
        for (id, standard, imp) in seeds {
            m.controls.insert(
                (*id).to_string(),
                NistControlEvidence {
                    standard_ref: (*standard).to_string(),
                    implementation_ref: (*imp).to_string(),
                },
            );
        }
        m
    }

    /// Inserts or updates a control evidence record
    pub fn insert(&mut self, control_id: impl Into<String>, evidence: NistControlEvidence) {
        self.controls.insert(control_id.into(), evidence);
    }

    /// Returns percentage of controls with evidence (0.0 – 1.0)
    pub fn score(&self) -> f64 {
        if self.controls.is_empty() {
            return 0.0;
        }
        let implemented = self.controls.len() as f64;
        let total = 20.0_f64.max(implemented);
        implemented / total
    }

    /// Returns the number of mapped controls
    pub fn len(&self) -> usize {
        self.controls.len()
    }

    /// Returns true if no controls are mapped
    pub fn is_empty(&self) -> bool {
        self.controls.is_empty()
    }
}

impl Default for NistControlMapper {
    fn default() -> Self {
        Self::new()
    }
}
