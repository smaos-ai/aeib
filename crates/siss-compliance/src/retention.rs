use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

/// Retention policy enforcing minimum and optional maximum data retention periods
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetentionPolicy {
    pub min_days: u32, // Minimum retention (180 days = 6 months, per EU AI Act Art. 12)
    pub max_days: u32, // Maximum retention (optional TTL)
    pub count_floor: u64, // Minimum retained record count (deletion blocked below this)
}

impl Default for RetentionPolicy {
    fn default() -> Self {
        Self {
            min_days: 180,
            max_days: 2555,  // ~7 years
            count_floor: 10, // Minimum 10 active records before deletes allowed
        }
    }
}

impl RetentionPolicy {
    /// Checks if data should still be retained (within minimum retention window)
    pub fn is_retained_valid(&self, created_at: DateTime<Utc>) -> bool {
        let min_retention = created_at + Duration::days(self.min_days as i64);
        Utc::now() < min_retention
    }

    /// Checks if data can be deleted (past minimum retention period)
    pub fn can_delete(&self, created_at: DateTime<Utc>) -> bool {
        !self.is_retained_valid(created_at)
    }

    /// Checks if deletion is allowed by count floor constraint
    /// Returns true only if current_count > count_floor (deletion blocked at or below floor)
    pub fn can_delete_by_count(&self, current_count: u64) -> bool {
        current_count > self.count_floor
    }
}
