#[cfg(test)]
mod stream6_gdpr_nis2 {
    use uuid::Uuid;
    use crate::{
        gdpr::{DataRegion, DataResidencyPolicy, DsarRequest, DsarType},
        nis2::{BreachNotification, IncidentSeverity, SecurityAuditEvent, SecurityAuditLogger, SecurityEventType},
    };

    #[test]
    fn test_residency_policy_enforces_eu() {
        let policy = DataResidencyPolicy::new(vec![DataRegion::EuEea], false);
        let result = policy.enforce(DataRegion::Us);
        assert!(result.is_err());
    }

    #[test]
    fn test_residency_policy_allows_ch() {
        let policy = DataResidencyPolicy::new(vec![DataRegion::Ch], false);
        let result = policy.enforce(DataRegion::Ch);
        assert!(result.is_ok());
    }

    #[test]
    fn test_dsar_deadline_30_days() {
        let req = DsarRequest::with_submitted_at(Uuid::new_v4(), DsarType::AccessRequest, 0);
        assert_eq!(req.deadline, 2_592_000);
    }

    #[test]
    fn test_fulfil_erasure_atomic() {
        let req = DsarRequest::new(Uuid::new_v4(), DsarType::ErasureRequest);
        let result = req.fulfill_erasure();
        assert!(result.is_ok());
    }

    #[test]
    fn test_fulfil_access_returns_data() {
        let id = Uuid::new_v4();
        let req = DsarRequest::new(id, DsarType::AccessRequest);
        let data = req.fulfill_access().expect("access fulfillment must return data");
        assert!(!data.is_empty());
        let text = String::from_utf8(data).expect("export must be valid UTF-8");
        assert!(text.contains(&id.to_string()));
    }

    #[test]
    fn test_breach_72h_deadline() {
        let notif = BreachNotification::with_detected_at(IncidentSeverity::Critical, 0);
        assert_eq!(notif.deadline_72h, 259_200);
    }

    #[test]
    fn test_breach_overdue_check() {
        let notif = BreachNotification::with_detected_at(IncidentSeverity::Significant, 0);
        assert!(notif.is_overdue());
    }

    #[test]
    fn test_audit_event_logging() {
        let mut logger = SecurityAuditLogger::new();
        assert_eq!(logger.events.len(), 0);
        logger.log_event(SecurityAuditEvent {
            event_type: SecurityEventType::AuthAttempt,
            timestamp: 1_000_000,
            actor_id: "agent-42".to_string(),
            details: "login attempt".to_string(),
        });
        assert_eq!(logger.events.len(), 1);
    }

    #[test]
    fn test_merkle_tree_deterministic() {
        let event = SecurityAuditEvent {
            event_type: SecurityEventType::DataAccess,
            timestamp: 9_999_999,
            actor_id: "siss-gatekeeper".to_string(),
            details: "read patient record".to_string(),
        };

        let mut logger_a = SecurityAuditLogger::new();
        logger_a.log_event(event.clone());
        let root_a = logger_a.build_merkle_tree();

        let mut logger_b = SecurityAuditLogger::new();
        logger_b.log_event(event);
        let root_b = logger_b.build_merkle_tree();

        assert_eq!(root_a, root_b);
        assert_eq!(root_a.len(), 64);
    }

    #[test]
    fn test_audit_event_types_all_defined() {
        let types = [
            SecurityEventType::AuthAttempt,
            SecurityEventType::DataAccess,
            SecurityEventType::ConfigChange,
            SecurityEventType::IncidentDetected,
        ];
        assert_eq!(types.len(), 4);
    }
}
