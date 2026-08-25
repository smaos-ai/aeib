use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Finance-specific ReBAC roles aligned to MiFID II
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FinanceRole {
    /// Chief Risk Officer, full control over execution venues and best execution rules
    ChiefRiskOfficer,
    /// Compliance officer, can audit trades and dispute resolution
    ComplianceOfficer,
    /// Trader, can execute trades subject to best execution policy
    Trader,
    /// Settlement operator, can confirm post-trade execution quality
    SettlementOperator,
}

/// MiFID II best-execution attributes (for AP2 evaluation)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BestExecutionAttributes {
    pub execution_venue: String,           // "LSE", "Euronext", "Dark Pool X"
    pub execution_price: f64,
    pub execution_time_ms: u64,            // Execution latency
    pub venue_fee_bps: i32,                // Fee in basis points
    pub post_trade_benchmark_price: f64,   // VWAP, median, etc.
    pub slippage_bps: i32,                 // (execution - benchmark) in bps
    pub notification_latency_ms: u64,      // Time to notify client
    pub liquidity_tier: String,            // "Top-Tier", "Secondary", "Illiquid"
    pub is_affiliate_venue: bool,          // Disclosure required by MiFID II
}

/// MiFID II audit context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiFIDIIAuditContext {
    pub trade_id: Uuid,
    pub trader_id: Uuid,
    pub order_time: chrono::DateTime<chrono::Utc>,
    pub execution_time: chrono::DateTime<chrono::Utc>,
    pub best_execution_attributes: BestExecutionAttributes,
    pub ap2_policy_decision: String, // "Allow" or "Deny"
    pub client_notification_sent: bool,
}

/// Generates a MiFID II-compliant role template
pub fn finance_role_template(role: FinanceRole) -> RoleTemplate {
    match role {
        FinanceRole::ChiefRiskOfficer => RoleTemplate {
            name: "MiFID II Chief Risk Officer".to_string(),
            can_approve_venues: true,
            can_modify_best_execution_policy: true,
            can_approve_affiliate_disclosures: true,
            audit_log_access: true,
            mfa_required: true,
            can_override_policy: true,
            override_requires_escalation: true,
        },
        FinanceRole::ComplianceOfficer => RoleTemplate {
            name: "MiFID II Compliance Officer".to_string(),
            can_approve_venues: false,
            can_modify_best_execution_policy: false,
            can_approve_affiliate_disclosures: false,
            audit_log_access: true,
            mfa_required: true,
            can_override_policy: false,
            override_requires_escalation: false,
        },
        FinanceRole::Trader => RoleTemplate {
            name: "Trader".to_string(),
            can_approve_venues: false,
            can_modify_best_execution_policy: false,
            can_approve_affiliate_disclosures: false,
            audit_log_access: false,
            mfa_required: true,
            can_override_policy: false,
            override_requires_escalation: false,
        },
        FinanceRole::SettlementOperator => RoleTemplate {
            name: "Settlement Operator".to_string(),
            can_approve_venues: false,
            can_modify_best_execution_policy: false,
            can_approve_affiliate_disclosures: false,
            audit_log_access: true,
            mfa_required: false,
            can_override_policy: false,
            override_requires_escalation: false,
        },
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoleTemplate {
    pub name: String,
    pub can_approve_venues: bool,
    pub can_modify_best_execution_policy: bool,
    pub can_approve_affiliate_disclosures: bool,
    pub audit_log_access: bool,
    pub mfa_required: bool,
    pub can_override_policy: bool,
    pub override_requires_escalation: bool,
}

/// Best-Execution Policy: validates trade attributes against MiFID II rules
pub fn evaluate_best_execution_policy(attrs: &BestExecutionAttributes) -> Result<(), String> {
    // RULE 1: Slippage limits per liquidity tier
    let slippage_limit = match attrs.liquidity_tier.as_str() {
        "Top-Tier" => 5,      // 5 bps for LSE top 300, etc.
        "Secondary" => 10,
        "Illiquid" => 20,
        _ => return Err("Unknown liquidity tier".to_string()),
    };

    if attrs.slippage_bps.abs() > slippage_limit {
        return Err(format!(
            "Slippage {} bps exceeds {} bps limit for {} liquidity",
            attrs.slippage_bps, slippage_limit, attrs.liquidity_tier
        ));
    }

    // RULE 2: Dark pool execution must not be significantly worse than public market
    if attrs.execution_venue.contains("Dark") {
        let dark_pool_penalty = 3; // bps
        if attrs.slippage_bps > dark_pool_penalty {
            return Err("Dark pool execution worse than public market benchmark".to_string());
        }
    }

    // RULE 3: Notification latency SLA
    if attrs.notification_latency_ms > 100 {
        return Err("Client notification exceeds 100ms SLA".to_string());
    }

    // RULE 4: Venue fee transparency (retail cap: 3 bps)
    let fee_cap = 3;
    if attrs.venue_fee_bps > fee_cap {
        return Err(format!("Venue fee {} bps exceeds retail cap", attrs.venue_fee_bps));
    }

    // RULE 5: No affiliate bias (same standards regardless of affiliate relationship)
    // (Enforced by running this rule regardless of is_affiliate flag)

    Ok(())
}

/// Generates affiliate disclosure text for MiFID II compliance
pub fn generate_affiliate_disclosure(
    trader: &str,
    venue: &str,
    affiliate_relationship: bool,
) -> String {
    if affiliate_relationship {
        format!(
            "AFFILIATE DISCLOSURE: Trader {} has a financial relationship with execution venue {}. \
             This execution was subject to the same best-execution standards as non-affiliated venues. \
             See audit trail for proof of equivalent execution quality.",
            trader, venue
        )
    } else {
        format!(
            "Trade executed at {} with full best-execution compliance verified by SovereignNexus governance capsule.",
            venue
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chief_risk_officer_can_modify_policy() {
        let role = finance_role_template(FinanceRole::ChiefRiskOfficer);
        assert!(role.can_modify_best_execution_policy);
        assert!(role.can_override_policy);
    }

    #[test]
    fn test_trader_cannot_modify_policy() {
        let role = finance_role_template(FinanceRole::Trader);
        assert!(!role.can_modify_best_execution_policy);
        assert!(!role.can_override_policy);
    }

    #[test]
    fn test_best_execution_accepts_good_execution() {
        let attrs = BestExecutionAttributes {
            execution_venue: "LSE".to_string(),
            execution_price: 100.0,
            execution_time_ms: 50,
            venue_fee_bps: 2,
            post_trade_benchmark_price: 100.02,
            slippage_bps: 2,
            notification_latency_ms: 50,
            liquidity_tier: "Top-Tier".to_string(),
            is_affiliate_venue: false,
        };
        assert!(evaluate_best_execution_policy(&attrs).is_ok());
    }

    #[test]
    fn test_best_execution_rejects_excessive_slippage() {
        let attrs = BestExecutionAttributes {
            execution_venue: "LSE".to_string(),
            execution_price: 100.0,
            execution_time_ms: 50,
            venue_fee_bps: 2,
            post_trade_benchmark_price: 100.1,
            slippage_bps: 15, // Exceeds 5 bps limit for Top-Tier
            notification_latency_ms: 50,
            liquidity_tier: "Top-Tier".to_string(),
            is_affiliate_venue: false,
        };
        assert!(evaluate_best_execution_policy(&attrs).is_err());
    }

    #[test]
    fn test_best_execution_rejects_slow_notification() {
        let attrs = BestExecutionAttributes {
            execution_venue: "LSE".to_string(),
            execution_price: 100.0,
            execution_time_ms: 50,
            venue_fee_bps: 2,
            post_trade_benchmark_price: 100.02,
            slippage_bps: 2,
            notification_latency_ms: 200, // Exceeds 100ms SLA
            liquidity_tier: "Top-Tier".to_string(),
            is_affiliate_venue: false,
        };
        assert!(evaluate_best_execution_policy(&attrs).is_err());
    }

    #[test]
    fn test_affiliate_disclosure_includes_relationship() {
        let disclosure = generate_affiliate_disclosure("trader_001", "Venue X", true);
        assert!(disclosure.contains("AFFILIATE DISCLOSURE"));
        assert!(disclosure.contains("trader_001"));
    }
}
