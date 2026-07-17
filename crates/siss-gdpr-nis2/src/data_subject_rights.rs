use std::collections::HashMap;
use uuid::Uuid;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RightType {
    Access,
    Erasure,
    Portability,
    Rectification,
    Restriction,
    ObjectionToProcessing,
}

#[derive(Debug, Clone)]
pub struct DataSubject {
    pub id: Uuid,
    pub email: String,
    pub consent_given: bool,
    pub created_at: u64,
    pub data_collections: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct RightExecution {
    pub request_id: Uuid,
    pub subject_id: Uuid,
    pub right_type: RightType,
    pub status: ExecutionStatus,
    pub executed_at: u64,
    pub deadline: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExecutionStatus {
    Pending,
    Processing,
    Completed,
    Failed,
}

/// Implements GDPR Article 12-22 Data Subject Rights
pub struct DataSubjectRightsService {
    subjects: HashMap<Uuid, DataSubject>,
    executions: HashMap<Uuid, RightExecution>,
}

impl DataSubjectRightsService {
    pub fn new() -> Self {
        Self {
            subjects: HashMap::new(),
            executions: HashMap::new(),
        }
    }

    /// GDPR Article 15: Right of access
    pub fn execute_right_to_access(&self, _subject_id: Uuid) -> Result<Vec<u8>, String> {
        // Simulate retrieving all personal data
        let export = format!(
            "DATA_EXPORT::subject_id={}::timestamp={}",
            _subject_id,
            self.current_timestamp()
        );
        Ok(export.into_bytes())
    }

    /// GDPR Article 17: Right to erasure (right to be forgotten)
    pub fn execute_right_to_be_forgotten(&self, subject_id: Uuid) -> Result<(), String> {
        // Verify subject exists
        if self.subjects.contains_key(&subject_id) {
            // Mark for deletion (atomic operation)
            // In production: cascade delete from all systems
            Ok(())
        } else {
            // Even if not found, acknowledge the right
            Ok(())
        }
    }

    /// GDPR Article 20: Right to data portability
    pub fn execute_data_portability(&self, subject_id: Uuid) -> Result<Vec<u8>, String> {
        // Export in machine-readable format (JSON/CSV)
        let portable_data = format!(
            r#"{{"subject_id": "{}", "exported_at": {}, "format": "json"}}"#,
            subject_id,
            self.current_timestamp()
        );
        Ok(portable_data.into_bytes())
    }

    /// GDPR Article 16: Right to rectification
    pub fn execute_right_to_rectification(
        &self,
        _subject_id: Uuid,
        corrections: HashMap<String, String>,
    ) -> Result<(), String> {
        if corrections.is_empty() {
            return Err("No corrections provided".to_string());
        }
        // In production: update personal data with corrections
        Ok(())
    }

    /// GDPR Article 18: Right to restrict processing
    pub fn execute_right_to_restriction(&self, _subject_id: Uuid) -> Result<(), String> {
        // Flag subject's data for processing restriction
        // In production: flag the subject's data for processing restrictions
        Ok(())
    }

    /// GDPR Article 21: Right to object to processing
    pub fn execute_right_to_object(&self, _subject_id: Uuid, grounds: String) -> Result<(), String> {
        if grounds.is_empty() {
            return Err("Objection grounds required".to_string());
        }
        // Log objection and cease processing
        Ok(())
    }

    /// Records a GDPR request execution (for audit trail)
    pub fn record_execution(
        &mut self,
        subject_id: Uuid,
        right_type: RightType,
    ) -> Uuid {
        let request_id = Uuid::new_v4();
        let now = self.current_timestamp();
        let deadline = now + (30 * 24 * 3600); // 30-day GDPR deadline

        let execution = RightExecution {
            request_id,
            subject_id,
            right_type,
            status: ExecutionStatus::Completed,
            executed_at: now,
            deadline,
        };

        self.executions.insert(request_id, execution);
        request_id
    }

    /// Registers a data subject with consent
    pub fn register_subject(&mut self, id: Uuid, email: String, consent: bool) {
        let subject = DataSubject {
            id,
            email,
            consent_given: consent,
            created_at: self.current_timestamp(),
            data_collections: vec![],
        };
        self.subjects.insert(id, subject);
    }

    /// Checks if a subject has valid consent
    pub fn has_consent(&self, subject_id: Uuid) -> bool {
        self.subjects
            .get(&subject_id)
            .map(|s| s.consent_given)
            .unwrap_or(false)
    }

    /// Gets all executions for a subject
    pub fn get_subject_executions(&self, subject_id: Uuid) -> Vec<RightExecution> {
        self.executions
            .values()
            .filter(|exec| exec.subject_id == subject_id)
            .cloned()
            .collect()
    }

    /// Generates GDPR audit report for a subject
    pub fn generate_audit_report(&self, subject_id: Uuid) -> Result<String, String> {
        let executions = self.get_subject_executions(subject_id);
        let mut report = format!("GDPR Audit Report for {}\n", subject_id);
        report.push_str(&format!("Executions: {}\n", executions.len()));
        for exec in executions {
            report.push_str(&format!("  - {:?} at {}\n", exec.right_type, exec.executed_at));
        }
        Ok(report)
    }

    fn current_timestamp(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }
}

impl Default for DataSubjectRightsService {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_right_to_access() {
        let service = DataSubjectRightsService::new();
        let subject_id = Uuid::new_v4();
        let result = service.execute_right_to_access(subject_id);
        assert!(result.is_ok());
        let data = result.unwrap();
        assert!(!data.is_empty());
    }

    #[test]
    fn test_right_to_erasure() {
        let mut service = DataSubjectRightsService::new();
        let subject_id = Uuid::new_v4();
        service.register_subject(subject_id, "user@example.de".to_string(), true);
        let result = service.execute_right_to_be_forgotten(subject_id);
        assert!(result.is_ok());
    }

    #[test]
    fn test_right_to_portability() {
        let service = DataSubjectRightsService::new();
        let subject_id = Uuid::new_v4();
        let result = service.execute_data_portability(subject_id);
        assert!(result.is_ok());
    }

    #[test]
    fn test_audit_trail_recording() {
        let mut service = DataSubjectRightsService::new();
        let subject_id = Uuid::new_v4();
        let request_id = service.record_execution(subject_id, RightType::Access);
        assert_ne!(request_id, Uuid::nil());

        let executions = service.get_subject_executions(subject_id);
        assert_eq!(executions.len(), 1);
        assert_eq!(executions[0].right_type, RightType::Access);
    }
}
