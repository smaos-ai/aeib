use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct TimeWindow {
    pub start_hour: u8,    // 0-23 UTC
    pub end_hour: u8,      // 0-23 UTC
    pub allowed: bool,     // true = allow in window, false = block
}

impl TimeWindow {
    pub fn new(start_hour: u8, end_hour: u8, allowed: bool) -> Result<Self, TemporalError> {
        if start_hour > 23 {
            return Err(TemporalError::InvalidStartHour(start_hour));
        }
        if end_hour > 23 {
            return Err(TemporalError::InvalidEndHour(end_hour));
        }
        Ok(Self {
            start_hour,
            end_hour,
            allowed,
        })
    }

    pub fn contains_hour(&self, hour: u8) -> bool {
        if self.start_hour <= self.end_hour {
            hour >= self.start_hour && hour < self.end_hour
        } else {
            // Wraps around midnight (e.g., 22-4)
            hour >= self.start_hour || hour < self.end_hour
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BlackoutDate {
    pub month: u8,         // 1-12
    pub day: u8,           // 1-31
    pub reason: String,
}

impl BlackoutDate {
    pub fn new(month: u8, day: u8, reason: String) -> Result<Self, TemporalError> {
        if !(1..=12).contains(&month) {
            return Err(TemporalError::InvalidMonth(month));
        }
        if !(1..=31).contains(&day) {
            return Err(TemporalError::InvalidDay(day));
        }
        Ok(Self { month, day, reason })
    }

    pub fn matches_date(&self, month: u8, day: u8) -> bool {
        self.month == month && self.day == day
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Decision {
    Allow,
    Deny,
}

#[derive(Debug, Error)]
pub enum TemporalError {
    #[error("invalid start hour: {0} (must be 0-23)")]
    InvalidStartHour(u8),

    #[error("invalid end hour: {0} (must be 0-23)")]
    InvalidEndHour(u8),

    #[error("invalid month: {0} (must be 1-12)")]
    InvalidMonth(u8),

    #[error("invalid day: {0} (must be 1-31)")]
    InvalidDay(u8),

    #[error("internal error: {0}")]
    InternalError(String),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_time_window_contains_hour() {
        let window = TimeWindow::new(9, 17, true).unwrap();
        assert!(window.contains_hour(9));
        assert!(window.contains_hour(10));
        assert!(window.contains_hour(16));
        assert!(!window.contains_hour(8));
        assert!(!window.contains_hour(17));
    }

    #[test]
    fn test_time_window_wraps_midnight() {
        let window = TimeWindow::new(22, 4, true).unwrap();
        assert!(window.contains_hour(22));
        assert!(window.contains_hour(23));
        assert!(window.contains_hour(0));
        assert!(window.contains_hour(3));
        assert!(!window.contains_hour(5));
        assert!(!window.contains_hour(10));
    }

    #[test]
    fn test_blackout_date_matches() {
        let blackout = BlackoutDate::new(12, 25, "Christmas".to_string()).unwrap();
        assert!(blackout.matches_date(12, 25));
        assert!(!blackout.matches_date(12, 26));
        assert!(!blackout.matches_date(1, 1));
    }

    #[test]
    fn test_time_window_invalid_hours() {
        assert!(TimeWindow::new(25, 30, true).is_err());
        assert!(TimeWindow::new(9, 25, true).is_err());
    }

    #[test]
    fn test_blackout_date_invalid_month_day() {
        assert!(BlackoutDate::new(13, 25, "Invalid".to_string()).is_err());
        assert!(BlackoutDate::new(12, 32, "Invalid".to_string()).is_err());
        assert!(BlackoutDate::new(0, 15, "Invalid".to_string()).is_err());
    }
}
