use chrono::{DateTime, Duration, Utc};
use parking_lot::Mutex;
use std::sync::Arc;
use uuid::Uuid;

use crate::types::LicenseEvent;

#[derive(Debug, Clone)]
pub struct AuditEntry {
    pub id: Uuid,
    pub event: LicenseEvent,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>, // 7 years retention
}

pub struct AuditTrail {
    entries: Arc<Mutex<Vec<AuditEntry>>>,
}

impl AuditTrail {
    pub fn new() -> Self {
        Self {
            entries: Arc::new(Mutex::new(Vec::new())),
        }
    }

    pub fn log(&self, event: LicenseEvent) {
        let now = Utc::now();
        let expires_at = now + Duration::days(365 * 7);

        let entry = AuditEntry {
            id: Uuid::new_v4(),
            event,
            created_at: now,
            expires_at,
        };

        let mut entries = self.entries.lock();
        entries.push(entry);
    }

    pub fn get_all(&self) -> Vec<AuditEntry> {
        let entries = self.entries.lock();
        entries.clone()
    }

    pub fn get_by_customer(&self, customer_id: Uuid) -> Vec<AuditEntry> {
        let entries = self.entries.lock();
        entries
            .iter()
            .filter(|entry| match &entry.event {
                LicenseEvent::Generated { customer_id: cid, .. } => cid == &customer_id,
                LicenseEvent::Revoked { customer_id: cid } => cid == &customer_id,
                LicenseEvent::PaymentReceived {
                    customer_id: cid, ..
                } => cid == &customer_id,
                _ => false,
            })
            .cloned()
            .collect()
    }

    pub fn count(&self) -> usize {
        let entries = self.entries.lock();
        entries.len()
    }

    pub fn retention_years(&self) -> i64 {
        7
    }
}

impl Default for AuditTrail {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for AuditTrail {
    fn clone(&self) -> Self {
        Self {
            entries: Arc::clone(&self.entries),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::Sku;

    #[test]
    fn test_audit_event_generated_logged() {
        let trail = AuditTrail::new();
        let customer_id = Uuid::new_v4();

        trail.log(LicenseEvent::Generated {
            customer_id,
            sku: Sku::Pro,
        });

        assert_eq!(trail.count(), 1);
        let entries = trail.get_all();
        assert_eq!(entries.len(), 1);
        assert!(matches!(
            &entries[0].event,
            LicenseEvent::Generated { sku: Sku::Pro, .. }
        ));
    }

    #[test]
    fn test_audit_event_validated_logged() {
        let trail = AuditTrail::new();
        let key = "SISS-Pro-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-20251225";

        trail.log(LicenseEvent::Validated {
            key: key.to_string(),
            result: true,
        });

        assert_eq!(trail.count(), 1);
    }

    #[test]
    fn test_audit_event_usage_recorded_logged() {
        let trail = AuditTrail::new();
        let key = "SISS-Starter-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-20251225";

        trail.log(LicenseEvent::UsageRecorded {
            key: key.to_string(),
            calls: 150,
        });

        assert_eq!(trail.count(), 1);
    }

    #[test]
    fn test_audit_event_revoked_logged() {
        let trail = AuditTrail::new();
        let customer_id = Uuid::new_v4();

        trail.log(LicenseEvent::Revoked { customer_id });

        assert_eq!(trail.count(), 1);
    }

    #[test]
    fn test_audit_trail_7_year_retention() {
        let trail = AuditTrail::new();
        let customer_id = Uuid::new_v4();

        trail.log(LicenseEvent::Generated {
            customer_id,
            sku: Sku::Enterprise,
        });

        let entries = trail.get_all();
        let entry = &entries[0];
        let retention_duration = entry.expires_at - entry.created_at;
        let expected_duration = Duration::days(365 * 7);

        assert!(retention_duration >= expected_duration - Duration::seconds(1));
        assert!(retention_duration <= expected_duration + Duration::seconds(1));
    }

    #[test]
    fn test_audit_trail_no_delete_method() {
        let trail = AuditTrail::new();
        trail.log(LicenseEvent::Generated {
            customer_id: Uuid::new_v4(),
            sku: Sku::Pro,
        });

        assert_eq!(trail.count(), 1);
    }

    #[test]
    fn test_audit_trail_immutable_once_logged() {
        let trail = AuditTrail::new();
        let customer_id = Uuid::new_v4();

        trail.log(LicenseEvent::Generated {
            customer_id,
            sku: Sku::Starter,
        });

        let entries1 = trail.get_all();
        let entry1_id = entries1[0].id;

        trail.log(LicenseEvent::Revoked { customer_id });

        let entries2 = trail.get_all();
        let entry2_id = entries2[0].id;

        assert_eq!(entry1_id, entry2_id);
        assert_eq!(entries2.len(), 2);
    }

    #[test]
    fn test_audit_trail_queryable_by_customer() {
        let trail = AuditTrail::new();
        let customer1 = Uuid::new_v4();
        let customer2 = Uuid::new_v4();

        trail.log(LicenseEvent::Generated {
            customer_id: customer1,
            sku: Sku::Pro,
        });

        trail.log(LicenseEvent::Generated {
            customer_id: customer2,
            sku: Sku::Starter,
        });

        trail.log(LicenseEvent::Revoked {
            customer_id: customer1,
        });

        let customer1_events = trail.get_by_customer(customer1);
        let customer2_events = trail.get_by_customer(customer2);

        assert_eq!(customer1_events.len(), 2);
        assert_eq!(customer2_events.len(), 1);
    }

    #[test]
    fn test_audit_trail_multiple_events() {
        let trail = AuditTrail::new();

        for _ in 0..10 {
            trail.log(LicenseEvent::Generated {
                customer_id: Uuid::new_v4(),
                sku: Sku::Pro,
            });
        }

        assert_eq!(trail.count(), 10);
    }

    #[test]
    fn test_audit_trail_retention_years_constant() {
        let trail = AuditTrail::new();
        assert_eq!(trail.retention_years(), 7);
    }

    #[test]
    fn test_audit_trail_payment_received_logged() {
        let trail = AuditTrail::new();
        let customer_id = Uuid::new_v4();

        trail.log(LicenseEvent::PaymentReceived {
            customer_id,
            amount_cents: 9999,
        });

        assert_eq!(trail.count(), 1);
        let entries = trail.get_by_customer(customer_id);
        assert_eq!(entries.len(), 1);
    }

    #[test]
    fn test_audit_entry_unique_ids() {
        let trail = AuditTrail::new();

        trail.log(LicenseEvent::Generated {
            customer_id: Uuid::new_v4(),
            sku: Sku::Pro,
        });

        trail.log(LicenseEvent::Generated {
            customer_id: Uuid::new_v4(),
            sku: Sku::Starter,
        });

        let entries = trail.get_all();
        assert_ne!(entries[0].id, entries[1].id);
    }

    #[test]
    fn test_audit_trail_cloneable() {
        let trail1 = AuditTrail::new();
        let customer_id = Uuid::new_v4();

        trail1.log(LicenseEvent::Generated {
            customer_id,
            sku: Sku::Enterprise,
        });

        let trail2 = trail1.clone();
        assert_eq!(trail2.count(), 1);

        trail2.log(LicenseEvent::Revoked { customer_id });
        assert_eq!(trail1.count(), 2);
        assert_eq!(trail2.count(), 2);
    }
}
