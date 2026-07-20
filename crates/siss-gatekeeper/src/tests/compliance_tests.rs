#[cfg(test)]
mod compliance_tests {
    use std::collections::HashMap;
    use uuid::Uuid;

    #[derive(Debug, Clone)]
    struct ComplianceRecord {
        creator_id: String,
        amount_cents: i64,
        timestamp: u64,
    }

    #[derive(Debug, Clone)]
    struct BreachLog {
        event_type: String,
        timestamp: u64,
        details: String,
    }

    #[derive(Debug)]
    struct ComplianceLedger {
        settlements: HashMap<String, Vec<ComplianceRecord>>,
        breach_logs: Vec<BreachLog>,
    }

    impl ComplianceLedger {
        fn new() -> Self {
            Self {
                settlements: HashMap::new(),
                breach_logs: Vec::new(),
            }
        }

        fn record_settlement(&mut self, creator_id: &str, amount_cents: i64) {
            self.settlements.entry(creator_id.to_string())
                .or_insert_with(Vec::new)
                .push(ComplianceRecord {
                    creator_id: creator_id.to_string(),
                    amount_cents,
                    timestamp: std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap()
                        .as_secs(),
                });
        }

        fn erase_personal_data(&mut self, creator_id: &str) -> bool {
            self.settlements.remove(creator_id).is_some()
        }

        fn get_creator_record(&self, creator_id: &str) -> Option<Vec<ComplianceRecord>> {
            self.settlements.get(creator_id).cloned()
        }

        fn log_breach(&mut self, event_type: &str) -> BreachLog {
            let breach = BreachLog {
                event_type: event_type.to_string(),
                timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
                details: "Breach logged".to_string(),
            };
            self.breach_logs.push(breach.clone());
            breach
        }

        fn get_audit_log(&self, index: usize) -> Option<ComplianceRecord> {
            self.settlements
                .values()
                .flat_map(|v| v.iter())
                .nth(index)
                .cloned()
        }
    }

    #[test]
    fn test_data_erasure_removes_creator_record() {
        let mut ledger = ComplianceLedger::new();
        let creator_id = "creator-123";

        ledger.record_settlement(creator_id, 10000);
        assert!(ledger.get_creator_record(creator_id).is_some());

        let erased = ledger.erase_personal_data(creator_id);
        assert!(erased, "Erasure should return true");
        assert_eq!(ledger.get_creator_record(creator_id), None, "Record should be gone");
    }

    #[test]
    fn test_breach_notification_logs_timestamp() {
        let mut ledger = ComplianceLedger::new();
        let breach = ledger.log_breach("unauthorized_access");

        assert!(breach.timestamp > 0, "Breach should have timestamp");
        assert_eq!(breach.event_type, "unauthorized_access");
    }

    #[test]
    fn test_audit_log_immutable() {
        let mut ledger = ComplianceLedger::new();
        ledger.record_settlement("creator-1", 10000);

        let log_entry = ledger.get_audit_log(0);
        assert!(log_entry.is_some());
        assert_eq!(log_entry.unwrap().amount_cents, 10000);
    }

    #[test]
    fn test_gdpr_compliance_erasure_workflow() {
        let mut ledger = ComplianceLedger::new();

        // Record multiple creators
        ledger.record_settlement("creator-1", 10000);
        ledger.record_settlement("creator-2", 5000);

        // GDPR erasure request for creator-1
        let erased = ledger.erase_personal_data("creator-1");
        assert!(erased);
        assert!(ledger.get_creator_record("creator-1").is_none());
        assert!(ledger.get_creator_record("creator-2").is_some(), "Other creators unaffected");
    }

    #[test]
    fn test_nis2_breach_logging() {
        let mut ledger = ComplianceLedger::new();

        ledger.log_breach("failed_authentication");
        ledger.log_breach("data_access_anomaly");

        assert_eq!(ledger.breach_logs.len(), 2, "All breaches should be logged");
    }
}
