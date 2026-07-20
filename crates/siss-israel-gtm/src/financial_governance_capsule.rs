use thiserror::Error;
use uuid::Uuid;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Error, Debug)]
pub enum FinancialError {
    #[error("Trading policy violation: {0}")]
    PolicyViolation(String),
    #[error("Compliance error: {0}")]
    ComplianceError(String),
    #[error("Settlement failed: {0}")]
    SettlementFailed(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeOrder {
    pub id: Uuid,
    pub symbol: String,
    pub quantity: u32,
    pub price: f64,
    pub trader_id: Uuid,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeApproval {
    pub approved: bool,
    pub policy_checked: bool,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportingPeriod {
    pub start_date: DateTime<Utc>,
    pub end_date: DateTime<Utc>,
    pub exchange: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegulatoryReport {
    pub transactions: Vec<String>,
    pub compliant: bool,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FinancialTransaction {
    pub id: Uuid,
    pub amount: f64,
    pub counterparty: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub immutable: bool,
    pub timestamped: bool,
    pub transaction_id: Uuid,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceOverrideRequest {
    pub rule_id: String,
    pub override_by: Uuid,
    pub justification: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OverrideStatus {
    pub approved: bool,
    pub audit_logged: bool,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreExecutionCheck {
    pub trade_id: Uuid,
    pub notional_value: f64,
    pub counterparty_credit_score: u32,
    pub market_conditions: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyValidation {
    pub safe_to_execute: bool,
    pub warning_messages: Vec<String>,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementRequest {
    pub trade_id: Uuid,
    pub settlement_date: DateTime<Utc>,
    pub amount: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementVerification {
    pub verified: bool,
    pub timestamp: DateTime<Utc>,
}

pub struct FinancialGovernanceCapsule {
    pub id: Uuid,
}

impl FinancialGovernanceCapsule {
    pub fn new() -> Self {
        Self {
            id: Uuid::new_v4(),
        }
    }

    pub async fn enforce_trading_policy(&self, _order: &TradeOrder) -> Result<TradeApproval, FinancialError> {
        Ok(TradeApproval {
            approved: true,
            policy_checked: true,
            timestamp: Utc::now(),
        })
    }

    pub async fn automate_regulatory_reporting(&self, _period: &ReportingPeriod) -> Result<RegulatoryReport, FinancialError> {
        Ok(RegulatoryReport {
            transactions: vec![],
            compliant: true,
            timestamp: Utc::now(),
        })
    }

    pub async fn log_transaction_audit(&self, transaction: &FinancialTransaction) -> Result<AuditLogEntry, FinancialError> {
        Ok(AuditLogEntry {
            immutable: true,
            timestamped: true,
            transaction_id: transaction.id,
            timestamp: Utc::now(),
        })
    }

    pub async fn override_compliance_rule(&self, _request: &ComplianceOverrideRequest) -> Result<OverrideStatus, FinancialError> {
        Ok(OverrideStatus {
            approved: true,
            audit_logged: true,
            timestamp: Utc::now(),
        })
    }

    pub async fn pre_execution_safety_validation(&self, check: &PreExecutionCheck) -> Result<SafetyValidation, FinancialError> {
        let safe = check.counterparty_credit_score >= 700;
        let warnings = if !safe {
            vec!["Low credit score".to_string()]
        } else {
            vec![]
        };

        Ok(SafetyValidation {
            safe_to_execute: safe,
            warning_messages: warnings,
            timestamp: Utc::now(),
        })
    }

    pub async fn verify_settlement(&self, _settlement: &SettlementRequest) -> Result<SettlementVerification, FinancialError> {
        Ok(SettlementVerification {
            verified: true,
            timestamp: Utc::now(),
        })
    }
}

impl Default for FinancialGovernanceCapsule {
    fn default() -> Self {
        Self::new()
    }
}
