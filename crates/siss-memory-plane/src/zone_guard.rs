//! Zone Guard: Access control for the tripartite zonal model
//!
//! Enforces boundary conditions between BlackFog, GrayFog, and VisibleField zones.
//! Prevents unauthorized transitions and data injection attacks.

use siss_context_cartography::types::MemoryEntry;
use siss_context_cartography::zones::ZoneClass;
use thiserror::Error;

/// Possible transitions between memory zones
#[derive(Debug, Clone, PartialEq)]
pub enum ZoneTransition {
    /// Data from BlackFog attempting to enter VisibleField directly
    BlackFogToVisible,
    /// Data from BlackFog entering GrayFog (confidence check required)
    BlackFogToGrayFog,
    /// Data from GrayFog entering VisibleField (confidence threshold check)
    GrayFogToVisible { confidence: f64 },
    /// Data already in VisibleField moving within it
    VisibleToVisible,
}

/// Violations of zone access policies
#[derive(Debug, Clone, PartialEq, Error)]
pub enum ZoneViolation {
    /// BlackFog data attempted direct injection into VisibleField
    #[error("BlackFog data attempted direct injection into VisibleField")]
    BlackFogBypass,
    /// GrayFog entry confidence below threshold
    #[error("GrayFog entry confidence {0} below threshold {1}")]
    BelowThreshold(f64, f64),
}

/// Guards access to memory zones based on confidence thresholds
#[derive(Debug, Clone)]
pub struct ZoneAccessGuard {
    /// Minimum confidence score required for entry into VisibleField
    pub confidence_threshold: f64,
}

impl ZoneAccessGuard {
    /// Create a new ZoneAccessGuard with the specified confidence threshold
    pub fn new(confidence_threshold: f64) -> Self {
        ZoneAccessGuard {
            confidence_threshold,
        }
    }

    /// Check if a zone transition is allowed
    pub fn check_transition(&self, transition: ZoneTransition) -> Result<(), ZoneViolation> {
        match transition {
            ZoneTransition::BlackFogToVisible => Err(ZoneViolation::BlackFogBypass),
            ZoneTransition::BlackFogToGrayFog => Err(ZoneViolation::BlackFogBypass),
            ZoneTransition::GrayFogToVisible { confidence } => {
                if confidence < self.confidence_threshold {
                    Err(ZoneViolation::BelowThreshold(
                        confidence,
                        self.confidence_threshold,
                    ))
                } else {
                    Ok(())
                }
            }
            ZoneTransition::VisibleToVisible => Ok(()),
        }
    }

    /// Guard entry of a single memory entry from a source zone
    pub fn guard_entry(
        &self,
        entry: &MemoryEntry,
        source_zone: &ZoneClass,
    ) -> Result<(), ZoneViolation> {
        let transition = match source_zone {
            ZoneClass::BlackFog => ZoneTransition::BlackFogToVisible,
            ZoneClass::GrayFog => ZoneTransition::GrayFogToVisible {
                confidence: entry.confidence_score,
            },
            ZoneClass::VisibleField => ZoneTransition::VisibleToVisible,
        };
        self.check_transition(transition)
    }

    /// Filter a batch of entries, returning only those that pass zone access checks
    pub fn filter_batch(&self, entries: Vec<(MemoryEntry, ZoneClass)>) -> Vec<MemoryEntry> {
        entries
            .into_iter()
            .filter_map(|(entry, zone)| self.guard_entry(&entry, &zone).ok().map(|_| entry))
            .collect()
    }
}
