use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Jurisdiction {
    Singapore,
    Japan,
    Korea,
}

impl Jurisdiction {
    pub fn code(&self) -> &'static str {
        match self {
            Jurisdiction::Singapore => "SG",
            Jurisdiction::Japan => "JP",
            Jurisdiction::Korea => "KR",
        }
    }

    pub fn regulator(&self) -> &'static str {
        match self {
            Jurisdiction::Singapore => "MAS",
            Jurisdiction::Japan => "FSA",
            Jurisdiction::Korea => "FSC",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ComplianceRule {
    KycRequired,
    AmlScreening,
    PEPScreening,
    TransactionLogging,
    AnnualReporting,
    CustomerDueDiligence,
    EnhancedDueDiligence,
}

impl ComplianceRule {
    pub fn description(&self) -> &'static str {
        match self {
            ComplianceRule::KycRequired => "Know Your Customer verification required",
            ComplianceRule::AmlScreening => "Anti-Money Laundering screening",
            ComplianceRule::PEPScreening => "Politically Exposed Person screening",
            ComplianceRule::TransactionLogging => "All transactions must be logged",
            ComplianceRule::AnnualReporting => "Annual compliance reporting required",
            ComplianceRule::CustomerDueDiligence => "Customer Due Diligence required",
            ComplianceRule::EnhancedDueDiligence => "Enhanced Due Diligence for high-risk",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceStatus {
    pub jurisdiction: String,
    pub entity_id: String,
    pub rules_enforced: Vec<String>,
    pub last_audit: Option<i64>,
    pub status: ComplianceCheckStatus,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ComplianceCheckStatus {
    Compliant,
    NonCompliant,
    PendingReview,
}

pub struct ComplianceEngine {
    rules_map: HashMap<String, Vec<ComplianceRule>>,
    entity_records: HashMap<String, ComplianceStatus>,
}

impl ComplianceEngine {
    pub fn new() -> Self {
        let mut engine = ComplianceEngine {
            rules_map: HashMap::new(),
            entity_records: HashMap::new(),
        };
        engine.initialize_rules();
        engine
    }

    fn initialize_rules(&mut self) {
        // Singapore MAS rules
        let sg_rules = vec![
            ComplianceRule::KycRequired,
            ComplianceRule::AmlScreening,
            ComplianceRule::PEPScreening,
            ComplianceRule::TransactionLogging,
            ComplianceRule::CustomerDueDiligence,
        ];
        self.rules_map.insert("SG".to_string(), sg_rules);

        // Japan FSA rules
        let jp_rules = vec![
            ComplianceRule::KycRequired,
            ComplianceRule::AmlScreening,
            ComplianceRule::TransactionLogging,
            ComplianceRule::AnnualReporting,
            ComplianceRule::CustomerDueDiligence,
        ];
        self.rules_map.insert("JP".to_string(), jp_rules);

        // Korea FSC rules
        let kr_rules = vec![
            ComplianceRule::KycRequired,
            ComplianceRule::AmlScreening,
            ComplianceRule::PEPScreening,
            ComplianceRule::TransactionLogging,
            ComplianceRule::EnhancedDueDiligence,
        ];
        self.rules_map.insert("KR".to_string(), kr_rules);
    }

    pub fn get_rules(&self, jurisdiction: Jurisdiction) -> Vec<ComplianceRule> {
        self.rules_map
            .get(jurisdiction.code())
            .cloned()
            .unwrap_or_default()
    }

    pub fn register_entity(
        &mut self,
        jurisdiction: Jurisdiction,
        entity_id: &str,
    ) -> crate::Result<ComplianceStatus> {
        let rules = self.get_rules(jurisdiction);

        let status = ComplianceStatus {
            jurisdiction: jurisdiction.code().to_string(),
            entity_id: entity_id.to_string(),
            rules_enforced: rules.iter().map(|r| format!("{:?}", r)).collect(),
            last_audit: None,
            status: ComplianceCheckStatus::PendingReview,
        };

        self.entity_records
            .insert(entity_id.to_string(), status.clone());
        Ok(status)
    }

    pub fn verify_compliance(&mut self, entity_id: &str) -> crate::Result<bool> {
        let record = self.entity_records.get_mut(entity_id).ok_or_else(|| {
            crate::ApacError::ComplianceError(format!("Entity not found: {}", entity_id))
        })?;

        let rules_count = record.rules_enforced.len();
        if rules_count >= 4 {
            record.status = ComplianceCheckStatus::Compliant;
            record.last_audit = Some(chrono::Utc::now().timestamp());
            Ok(true)
        } else {
            record.status = ComplianceCheckStatus::NonCompliant;
            Ok(false)
        }
    }

    pub fn get_compliance_status(&self, entity_id: &str) -> Option<ComplianceStatus> {
        self.entity_records.get(entity_id).cloned()
    }

    pub fn audit_trail(&self, entity_id: &str) -> crate::Result<ComplianceStatus> {
        self.entity_records.get(entity_id).cloned().ok_or_else(|| {
            crate::ApacError::ComplianceError(format!("No audit trail for entity: {}", entity_id))
        })
    }

    pub fn enforce_rule(&mut self, entity_id: &str, rule: ComplianceRule) -> crate::Result<()> {
        let record = self.entity_records.get_mut(entity_id).ok_or_else(|| {
            crate::ApacError::ComplianceError(format!("Entity not found: {}", entity_id))
        })?;

        let rule_name = format!("{:?}", rule);
        if !record.rules_enforced.contains(&rule_name) {
            record.rules_enforced.push(rule_name);
        }
        Ok(())
    }

    pub fn is_compliant(&self, entity_id: &str) -> bool {
        self.entity_records
            .get(entity_id)
            .map(|record| record.status == ComplianceCheckStatus::Compliant)
            .unwrap_or(false)
    }
}

impl Default for ComplianceEngine {
    fn default() -> Self {
        Self::new()
    }
}
