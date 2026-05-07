// ReBAC evaluation logic lives in edge/rebac.rs.
// This module re-exports for the invariant API surface.
pub use crate::edge::rebac::{evaluate_access, AccessDecision};
