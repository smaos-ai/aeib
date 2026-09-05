use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum DataRegion {
    EuEea,
    Us,
    Ch,
    Other,
}

pub struct DataResidencyPolicy {
    pub allowed_regions: Vec<DataRegion>,
    pub dpia_required: bool,
}

impl DataResidencyPolicy {
    pub fn new(allowed_regions: Vec<DataRegion>, dpia_required: bool) -> Self {
        Self {
            allowed_regions,
            dpia_required,
        }
    }

    pub fn enforce(&self, data_location: DataRegion) -> Result<(), String> {
        if self.allowed_regions.contains(&data_location) {
            Ok(())
        } else {
            Err(format!(
                "Data residency violation: {:?} is not in allowed regions {:?}",
                data_location, self.allowed_regions
            ))
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DsarType {
    AccessRequest,
    ErasureRequest,
    ExportRequest,
}

pub struct DsarRequest {
    pub subject_id: Uuid,
    pub request_type: DsarType,
    pub submitted_at: u64,
    pub deadline: u64,
}

const THIRTY_DAYS_SECS: u64 = 30 * 24 * 3600;

impl DsarRequest {
    pub fn new(subject_id: Uuid, request_type: DsarType) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        Self {
            subject_id,
            request_type,
            submitted_at: now,
            deadline: now + THIRTY_DAYS_SECS,
        }
    }

    pub fn with_submitted_at(subject_id: Uuid, request_type: DsarType, submitted_at: u64) -> Self {
        Self {
            subject_id,
            request_type,
            submitted_at,
            deadline: submitted_at + THIRTY_DAYS_SECS,
        }
    }

    pub fn is_within_deadline(&self) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        now <= self.deadline
    }

    pub fn fulfill_access(&self) -> Result<Vec<u8>, String> {
        let payload = format!("encrypted_export::{}", self.subject_id);
        Ok(payload.into_bytes())
    }

    pub fn fulfill_erasure(&self) -> Result<(), String> {
        Ok(())
    }
}
