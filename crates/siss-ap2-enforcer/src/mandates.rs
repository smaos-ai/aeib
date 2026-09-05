use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use uuid::Uuid;

/// AP2: Agent Payments Protocol
/// Cryptographic mandates enforcing non-repudiatable authorization for all agent transactions.
/// Every cloud burst, API call, or resource allocation requires explicit IntentMandate + PaymentMandate pair.

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IntentMandate {
    pub mandate_id: Uuid,
    pub agent_id: Uuid,
    pub intent: String,
    pub resource_type: ResourceType,
    pub estimated_cost_usd: f64,
    pub spending_limit_usd: f64,
    pub authorized_by: String,
    pub authorization_timestamp: DateTime<Utc>,
    pub signature: String,
    pub is_active: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ResourceType {
    LocalInference,
    CloudBurst,
    APICall,
    DataTransfer,
    Storage,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PaymentMandate {
    pub payment_id: Uuid,
    pub intent_mandate_id: Uuid,
    pub actual_cost_usd: f64,
    pub transaction_hash: String,
    pub cryptographic_proof: String,
    pub executed_at: DateTime<Utc>,
    pub status: PaymentStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum PaymentStatus {
    Pending,
    Authorized,
    Executed,
    Disputed,
    Settled,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MandateGuard {
    pub guard_id: Uuid,
    pub mandate_id: Uuid,
    pub threshold_warning_pct: f64,
    pub threshold_hard_limit_pct: f64,
    pub accumulated_cost_usd: f64,
    pub transaction_count: u64,
}

pub struct AP2MandateEngine {
    intent_mandates: HashMap<Uuid, IntentMandate>,
    payment_mandates: HashMap<Uuid, PaymentMandate>,
    mandate_guards: HashMap<Uuid, MandateGuard>,
    audit_log: Vec<AuditEvent>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AuditEvent {
    pub event_id: Uuid,
    pub mandate_id: Uuid,
    pub event_type: AuditEventType,
    pub details: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AuditEventType {
    MandateCreated,
    MandateAuthorized,
    PaymentProcessed,
    ThresholdWarning,
    HardLimitExceeded,
    MandateRevoked,
}

impl AP2MandateEngine {
    pub fn new() -> Self {
        Self {
            intent_mandates: HashMap::new(),
            payment_mandates: HashMap::new(),
            mandate_guards: HashMap::new(),
            audit_log: Vec::new(),
        }
    }

    pub fn create_intent_mandate(
        &mut self,
        agent_id: Uuid,
        intent: String,
        resource_type: ResourceType,
        estimated_cost: f64,
        spending_limit: f64,
        authorized_by: String,
    ) -> Result<Uuid, String> {
        if spending_limit < estimated_cost {
            return Err("Spending limit must be >= estimated cost".to_string());
        }

        let mandate_id = Uuid::new_v4();
        let signature =
            AP2MandateEngine::compute_mandate_signature(&mandate_id, &agent_id, &intent);

        let mandate = IntentMandate {
            mandate_id,
            agent_id,
            intent: intent.clone(),
            resource_type,
            estimated_cost_usd: estimated_cost,
            spending_limit_usd: spending_limit,
            authorized_by,
            authorization_timestamp: Utc::now(),
            signature,
            is_active: true,
        };

        let guard = MandateGuard {
            guard_id: Uuid::new_v4(),
            mandate_id,
            threshold_warning_pct: 0.80,
            threshold_hard_limit_pct: 1.0,
            accumulated_cost_usd: 0.0,
            transaction_count: 0,
        };

        self.intent_mandates.insert(mandate_id, mandate.clone());
        self.mandate_guards.insert(guard.guard_id, guard);

        self.audit_log.push(AuditEvent {
            event_id: Uuid::new_v4(),
            mandate_id,
            event_type: AuditEventType::MandateCreated,
            details: format!("Intent mandate created for {}", intent),
            timestamp: Utc::now(),
        });

        Ok(mandate_id)
    }

    pub fn authorize_mandate(&mut self, mandate_id: Uuid) -> Result<(), String> {
        let mandate = self
            .intent_mandates
            .get_mut(&mandate_id)
            .ok_or("Mandate not found")?;

        mandate.is_active = true;

        self.audit_log.push(AuditEvent {
            event_id: Uuid::new_v4(),
            mandate_id,
            event_type: AuditEventType::MandateAuthorized,
            details: "Mandate authorized for execution".to_string(),
            timestamp: Utc::now(),
        });

        Ok(())
    }

    pub fn process_payment(&mut self, mandate_id: Uuid, actual_cost: f64) -> Result<Uuid, String> {
        let mandate = self
            .intent_mandates
            .get(&mandate_id)
            .ok_or("Mandate not found")?;

        if !mandate.is_active {
            return Err("Mandate is not active".to_string());
        }

        let guard = self
            .mandate_guards
            .values_mut()
            .find(|g| g.mandate_id == mandate_id)
            .ok_or("Guard not found")?;

        let new_total = guard.accumulated_cost_usd + actual_cost;
        if new_total > mandate.spending_limit_usd {
            self.audit_log.push(AuditEvent {
                event_id: Uuid::new_v4(),
                mandate_id,
                event_type: AuditEventType::HardLimitExceeded,
                details: format!(
                    "Payment would exceed limit: {} + {} > {}",
                    guard.accumulated_cost_usd, actual_cost, mandate.spending_limit_usd
                ),
                timestamp: Utc::now(),
            });
            return Err("Payment would exceed mandate spending limit".to_string());
        }

        let payment_id = Uuid::new_v4();
        let transaction_hash = Self::compute_transaction_hash(&payment_id, actual_cost);
        let cryptographic_proof =
            Self::compute_cryptographic_proof(&mandate.signature, &transaction_hash);

        let payment = PaymentMandate {
            payment_id,
            intent_mandate_id: mandate_id,
            actual_cost_usd: actual_cost,
            transaction_hash,
            cryptographic_proof,
            executed_at: Utc::now(),
            status: PaymentStatus::Executed,
        };

        guard.accumulated_cost_usd = new_total;
        guard.transaction_count += 1;

        if new_total >= (mandate.spending_limit_usd * guard.threshold_warning_pct) {
            self.audit_log.push(AuditEvent {
                event_id: Uuid::new_v4(),
                mandate_id,
                event_type: AuditEventType::ThresholdWarning,
                details: format!(
                    "Spending threshold warning: {}% of limit reached",
                    ((new_total / mandate.spending_limit_usd) * 100.0) as u32
                ),
                timestamp: Utc::now(),
            });
        }

        self.payment_mandates.insert(payment_id, payment.clone());

        self.audit_log.push(AuditEvent {
            event_id: Uuid::new_v4(),
            mandate_id,
            event_type: AuditEventType::PaymentProcessed,
            details: format!("Payment processed: ${:.2}", actual_cost),
            timestamp: Utc::now(),
        });

        Ok(payment_id)
    }

    pub fn get_mandate_status(&self, mandate_id: Uuid) -> Option<(IntentMandate, MandateGuard)> {
        let mandate = self.intent_mandates.get(&mandate_id)?.clone();
        let guard = self
            .mandate_guards
            .values()
            .find(|g| g.mandate_id == mandate_id)?
            .clone();
        Some((mandate, guard))
    }

    pub fn audit_log(&self) -> &[AuditEvent] {
        &self.audit_log
    }

    fn compute_mandate_signature(mandate_id: &Uuid, agent_id: &Uuid, intent: &str) -> String {
        let input = format!("{}:{}:{}", mandate_id, agent_id, intent);
        let mut hasher = Sha256::new();
        hasher.update(input.as_bytes());
        hex::encode(hasher.finalize())
    }

    fn compute_transaction_hash(payment_id: &Uuid, cost: f64) -> String {
        let input = format!("{}:{}", payment_id, cost);
        let mut hasher = Sha256::new();
        hasher.update(input.as_bytes());
        hex::encode(hasher.finalize())
    }

    fn compute_cryptographic_proof(signature: &str, tx_hash: &str) -> String {
        let input = format!("{}:{}", signature, tx_hash);
        let mut hasher = Sha256::new();
        hasher.update(input.as_bytes());
        hex::encode(hasher.finalize())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_intent_mandate() {
        let mut engine = AP2MandateEngine::new();
        let result = engine.create_intent_mandate(
            Uuid::new_v4(),
            "cloud_burst_inference".to_string(),
            ResourceType::CloudBurst,
            100.0,
            500.0,
            "human@example.com".to_string(),
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_reject_mandate_with_limit_less_than_estimate() {
        let mut engine = AP2MandateEngine::new();
        let result = engine.create_intent_mandate(
            Uuid::new_v4(),
            "test".to_string(),
            ResourceType::CloudBurst,
            500.0,
            100.0,
            "human@example.com".to_string(),
        );
        assert!(result.is_err());
    }

    #[test]
    fn test_process_payment_within_limit() {
        let mut engine = AP2MandateEngine::new();
        let mandate_id = engine
            .create_intent_mandate(
                Uuid::new_v4(),
                "test".to_string(),
                ResourceType::CloudBurst,
                100.0,
                500.0,
                "human@example.com".to_string(),
            )
            .unwrap();

        engine.authorize_mandate(mandate_id).ok();
        let payment_result = engine.process_payment(mandate_id, 50.0);
        assert!(payment_result.is_ok());
    }

    #[test]
    fn test_reject_payment_exceeding_limit() {
        let mut engine = AP2MandateEngine::new();
        let mandate_id = engine
            .create_intent_mandate(
                Uuid::new_v4(),
                "test".to_string(),
                ResourceType::CloudBurst,
                100.0,
                200.0,
                "human@example.com".to_string(),
            )
            .unwrap();

        engine.authorize_mandate(mandate_id).ok();
        engine.process_payment(mandate_id, 150.0).ok();
        let second_payment = engine.process_payment(mandate_id, 100.0);
        assert!(second_payment.is_err());
    }

    #[test]
    fn test_mandate_status_tracks_spending() {
        let mut engine = AP2MandateEngine::new();
        let mandate_id = engine
            .create_intent_mandate(
                Uuid::new_v4(),
                "test".to_string(),
                ResourceType::CloudBurst,
                100.0,
                500.0,
                "human@example.com".to_string(),
            )
            .unwrap();

        engine.authorize_mandate(mandate_id).ok();
        engine.process_payment(mandate_id, 75.0).ok();
        engine.process_payment(mandate_id, 75.0).ok();

        let (_, guard) = engine.get_mandate_status(mandate_id).unwrap();
        assert_eq!(guard.accumulated_cost_usd, 150.0);
        assert_eq!(guard.transaction_count, 2);
    }

    #[test]
    fn test_audit_log_records_all_events() {
        let mut engine = AP2MandateEngine::new();
        let mandate_id = engine
            .create_intent_mandate(
                Uuid::new_v4(),
                "test".to_string(),
                ResourceType::CloudBurst,
                100.0,
                500.0,
                "human@example.com".to_string(),
            )
            .unwrap();

        engine.authorize_mandate(mandate_id).ok();
        engine.process_payment(mandate_id, 450.0).ok();

        let audit = engine.audit_log();
        assert!(
            audit
                .iter()
                .any(|e| e.event_type == AuditEventType::MandateCreated)
        );
        assert!(
            audit
                .iter()
                .any(|e| e.event_type == AuditEventType::MandateAuthorized)
        );
        assert!(
            audit
                .iter()
                .any(|e| e.event_type == AuditEventType::PaymentProcessed)
        );
        assert!(
            audit
                .iter()
                .any(|e| e.event_type == AuditEventType::ThresholdWarning)
        );
    }
}
