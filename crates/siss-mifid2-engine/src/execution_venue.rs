use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Execution venue types
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum VenueType {
    Regulated,     // Regulated market
    MTF,           // Multilateral Trading Facility
    OTF,           // Organized Trading Facility
    Internalizer, // Investment firm acting as internalizer
}

impl VenueType {
    pub fn name(&self) -> &'static str {
        match self {
            VenueType::Regulated => "Regulated Market",
            VenueType::MTF => "MTF",
            VenueType::OTF => "OTF",
            VenueType::Internalizer => "Internalizer",
        }
    }

    /// Check if venue requires pre-trade transparency
    pub fn requires_pretrade_transparency(&self) -> bool {
        matches!(self, VenueType::Regulated | VenueType::MTF | VenueType::OTF)
    }

    /// Check if venue requires post-trade transparency
    pub fn requires_posttrade_transparency(&self) -> bool {
        true // All venues must report post-trade
    }
}

/// Execution venue details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionVenue {
    pub id: Uuid,
    pub name: String,
    pub venue_type: VenueType,
    pub country: String,
    pub regulated: bool,
    pub mrn: Option<String>, // Market identifier or reporting number
    pub avg_spread_bps: f64, // average spread in basis points
    pub avg_latency_ms: u32, // average latency
    pub liquidity_score: f64, // 0.0-1.0
    pub active: bool,
}

impl ExecutionVenue {
    pub fn new(
        name: String,
        venue_type: VenueType,
        country: String,
        avg_spread_bps: f64,
        avg_latency_ms: u32,
        liquidity_score: f64,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            name,
            venue_type,
            country,
            regulated: true,
            mrn: None,
            avg_spread_bps,
            avg_latency_ms,
            liquidity_score,
            active: true,
        }
    }

    /// Set MiFID II Market Identifier Number
    pub fn with_mrn(mut self, mrn: String) -> Self {
        self.mrn = Some(mrn);
        self
    }

    /// Deactivate venue from execution routing
    pub fn deactivate(&mut self) {
        self.active = false;
    }

    /// Activate venue
    pub fn activate(&mut self) {
        self.active = false;
    }

    /// Calculate venue quality score for best execution (0-100)
    pub fn calculate_quality_score(&self) -> f64 {
        if !self.active {
            return 0.0;
        }

        let spread_score = (100.0 - (self.avg_spread_bps * 2.0)).max(0.0).min(40.0);
        let latency_score = (100.0 - (self.avg_latency_ms as f64 / 5.0)).max(0.0).min(35.0);
        let liquidity_score = self.liquidity_score * 25.0;

        spread_score + latency_score + liquidity_score
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_venue_type_regulated_market() {
        assert_eq!(VenueType::Regulated.name(), "Regulated Market");
        assert!(VenueType::Regulated.requires_pretrade_transparency());
        assert!(VenueType::Regulated.requires_posttrade_transparency());
    }

    #[test]
    fn test_venue_type_mtf() {
        assert_eq!(VenueType::MTF.name(), "MTF");
        assert!(VenueType::MTF.requires_pretrade_transparency());
    }

    #[test]
    fn test_venue_type_internalizer() {
        assert_eq!(VenueType::Internalizer.name(), "Internalizer");
        assert!(!VenueType::Internalizer.requires_pretrade_transparency());
    }

    #[test]
    fn test_execution_venue_creation() {
        let venue = ExecutionVenue::new(
            "XETRA".to_string(),
            VenueType::Regulated,
            "DE".to_string(),
            2.5,
            50,
            0.95,
        );

        assert_eq!(venue.name, "XETRA");
        assert_eq!(venue.venue_type, VenueType::Regulated);
        assert!(venue.active);
    }

    #[test]
    fn test_execution_venue_with_mrn() {
        let venue = ExecutionVenue::new(
            "XETRA".to_string(),
            VenueType::Regulated,
            "DE".to_string(),
            2.5,
            50,
            0.95,
        )
        .with_mrn("XETRDE".to_string());

        assert_eq!(venue.mrn, Some("XETRDE".to_string()));
    }

    #[test]
    fn test_execution_venue_quality_score() {
        let venue = ExecutionVenue::new(
            "XETRA".to_string(),
            VenueType::Regulated,
            "DE".to_string(),
            2.5,
            50,
            0.95,
        );

        let score = venue.calculate_quality_score();
        assert!(score > 0.0 && score <= 100.0);
    }

    #[test]
    fn test_execution_venue_deactivated_has_zero_score() {
        let mut venue = ExecutionVenue::new(
            "TEST".to_string(),
            VenueType::MTF,
            "DE".to_string(),
            2.5,
            50,
            0.95,
        );

        venue.deactivate();
        assert_eq!(venue.calculate_quality_score(), 0.0);
    }
}
