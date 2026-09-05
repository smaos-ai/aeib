use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Pilot Agreement Template (€50K–€150K, 3-month term)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PilotAgreement {
    pub customer_name: String,
    pub pilot_duration_days: u32,
    pub pilot_fee_eur: u32,
    pub scope_of_work: Vec<String>,
    pub success_criteria: Vec<String>,
    pub payment_schedule: PaymentSchedule,
    pub sla: ServiceLevelAgreement,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaymentSchedule {
    pub amount_eur: u32,
    pub payment_1_pct: u32,          // % due on signature
    pub payment_1_days: u32,         // Days after signature
    pub payment_2_pct: u32,          // % due on milestone
    pub payment_2_days: u32,
    pub payment_3_pct: u32,          // % due on completion
    pub payment_3_days: u32,
}

/// Annual Master Service Agreement (€300K–€600K/year)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnnualMSA {
    pub customer_name: String,
    pub term_start: chrono::DateTime<chrono::Utc>,
    pub term_end: chrono::DateTime<chrono::Utc>,
    pub annual_fee_eur: u32,
    pub included_features: Vec<String>,
    pub support_tier: SupportTier,
    pub sla: ServiceLevelAgreement,
    pub renewal_terms: RenewalTerms,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SupportTier {
    Standard,   // 8x5 email support, 24-hour response
    Premium,    // 24x7 phone + email, 4-hour response, dedicated account manager
    Enterprise, // 24x7 phone + dedicated engineer, 1-hour response
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenewalTerms {
    pub auto_renew: bool,
    pub renewal_notice_days: u32,
    pub price_escalation_pct: f32, // Typically 3-5%
}

/// Service Level Agreement (SLA) — applies to both pilot and annual contracts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceLevelAgreement {
    pub uptime_sla_pct: f32,               // Target: 99.5%
    pub audit_availability_sla_pct: f32,   // Target: 99.9%
    pub response_time_hours: u32,          // Support response time
    pub maintenance_window_hours_per_month: u32,
    pub penalties: PenaltyStructure,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PenaltyStructure {
    pub uptime_below_99_5_pct_credit: f32,  // % of monthly fee, e.g., 5%
    pub uptime_below_99_pct_credit: f32,    // % of monthly fee, e.g., 10%
    pub uptime_below_95_pct_credit: f32,    // % of monthly fee, e.g., 25%
    pub max_monthly_credit_pct: f32,        // Cap at 30% of monthly fee
}

/// Pilot Agreement templates by vertical
pub fn defense_pilot_agreement() -> PilotAgreement {
    PilotAgreement {
        customer_name: "[Defense Prime Name]".to_string(),
        pilot_duration_days: 90,
        pilot_fee_eur: 120_000,
        scope_of_work: vec![
            "Deploy behavioral firewall on customer test environment".to_string(),
            "Integrate with 1 AI decision pipeline (swarm coordination or mission replay)".to_string(),
            "Deliver audit trail, deterministic replay, behavioral anomaly detection".to_string(),
        ],
        success_criteria: vec![
            "100% audit coverage of target decision pipeline".to_string(),
            "<10ms governance overhead measured in production".to_string(),
            "Zero false-positive policy blocks in 2-week production run".to_string(),
        ],
        payment_schedule: PaymentSchedule {
            amount_eur: 120_000,
            payment_1_pct: 40,
            payment_1_days: 0, // Due on signature
            payment_2_pct: 40,
            payment_2_days: 45, // Due on milestone (pilot day 45)
            payment_3_pct: 20,
            payment_3_days: 90, // Due on completion
        },
        sla: defense_sla(),
    }
}

pub fn healthcare_pilot_agreement() -> PilotAgreement {
    PilotAgreement {
        customer_name: "[Healthcare Provider Name]".to_string(),
        pilot_duration_days: 90,
        pilot_fee_eur: 100_000,
        scope_of_work: vec![
            "Deploy governance capsule on customer HIPAA-compliant infrastructure".to_string(),
            "Integrate with patient access log ingestion (validate minimum necessary checks)".to_string(),
            "Deliver breach detection playbook + incident response simulation".to_string(),
        ],
        success_criteria: vec![
            "100% audit coverage of PHI access (patient IDs, data elements, timestamp)".to_string(),
            "Breach detection system identifies 10/10 simulated anomalies".to_string(),
            "Incident response workflow tested (alert → investigation → remediation)".to_string(),
        ],
        payment_schedule: PaymentSchedule {
            amount_eur: 100_000,
            payment_1_pct: 40,
            payment_1_days: 0,
            payment_2_pct: 40,
            payment_2_days: 45,
            payment_3_pct: 20,
            payment_3_days: 90,
        },
        sla: healthcare_sla(),
    }
}

pub fn finance_pilot_agreement() -> PilotAgreement {
    PilotAgreement {
        customer_name: "[Financial Institution Name]".to_string(),
        pilot_duration_days: 90,
        pilot_fee_eur: 150_000,
        scope_of_work: vec![
            "Deploy governance capsule on customer trading desk infrastructure".to_string(),
            "Integrate with order management system (OMS) for pre-execution best-execution checks".to_string(),
            "Deliver MiFID II audit export (EMIR TR-compatible format)".to_string(),
        ],
        success_criteria: vec![
            "100% best-execution policy evaluation on 1000+ test trades".to_string(),
            "MiFID II audit export generates correct EMIR TR fields for 100 sample trades".to_string(),
            "Dispute resolution workflow tested: policy re-evaluation + refund calculation".to_string(),
        ],
        payment_schedule: PaymentSchedule {
            amount_eur: 150_000,
            payment_1_pct: 40,
            payment_1_days: 0,
            payment_2_pct: 40,
            payment_2_days: 45,
            payment_3_pct: 20,
            payment_3_days: 90,
        },
        sla: finance_sla(),
    }
}

fn defense_sla() -> ServiceLevelAgreement {
    ServiceLevelAgreement {
        uptime_sla_pct: 99.5,
        audit_availability_sla_pct: 99.9,
        response_time_hours: 4, // FedRAMP security incidents require 4-hour response
        maintenance_window_hours_per_month: 2,
        penalties: PenaltyStructure {
            uptime_below_99_5_pct_credit: 5.0,
            uptime_below_99_pct_credit: 10.0,
            uptime_below_95_pct_credit: 25.0,
            max_monthly_credit_pct: 30.0,
        },
    }
}

fn healthcare_sla() -> ServiceLevelAgreement {
    ServiceLevelAgreement {
        uptime_sla_pct: 99.5,
        audit_availability_sla_pct: 99.9,
        response_time_hours: 2, // HIPAA breach response requires alerting
        maintenance_window_hours_per_month: 2,
        penalties: PenaltyStructure {
            uptime_below_99_5_pct_credit: 7.5,
            uptime_below_99_pct_credit: 15.0,
            uptime_below_95_pct_credit: 30.0,
            max_monthly_credit_pct: 30.0,
        },
    }
}

fn finance_sla() -> ServiceLevelAgreement {
    ServiceLevelAgreement {
        uptime_sla_pct: 99.9, // Trading systems require higher availability
        audit_availability_sla_pct: 99.95,
        response_time_hours: 1, // MiFID II compliance cannot tolerate extended downtime
        maintenance_window_hours_per_month: 1,
        penalties: PenaltyStructure {
            uptime_below_99_9_pct_credit: 10.0,
            uptime_below_99_5_pct_credit: 20.0,
            uptime_below_99_pct_credit: 50.0,
            max_monthly_credit_pct: 50.0, // Higher cap for financial services
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_defense_pilot_agreement_structure() {
        let pilot = defense_pilot_agreement();
        assert_eq!(pilot.pilot_duration_days, 90);
        assert_eq!(pilot.pilot_fee_eur, 120_000);
        assert_eq!(pilot.payment_schedule.payment_1_pct, 40);
    }

    #[test]
    fn test_healthcare_pilot_has_correct_fee() {
        let pilot = healthcare_pilot_agreement();
        assert_eq!(pilot.pilot_fee_eur, 100_000);
    }

    #[test]
    fn test_finance_pilot_has_highest_fee() {
        let finance = finance_pilot_agreement();
        let defense = defense_pilot_agreement();
        assert!(finance.pilot_fee_eur > defense.pilot_fee_eur);
    }

    #[test]
    fn test_sla_penalties_do_not_exceed_cap() {
        let sla = defense_sla();
        assert!(sla.penalties.uptime_below_95_pct_credit <= sla.penalties.max_monthly_credit_pct);
    }
}
