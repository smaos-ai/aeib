//! L1: Policy-bound reasoning with EU AI Act enforcement
//! Ensures Claude decisions cite and respect Article 50 + Annex III/I requirements

pub mod contracts;
pub mod error;
pub mod policy;

pub use contracts::{L1Input, L1Output, PolicyDecision, PolicyRequest};
pub use error::{L1AuditEntry, L1Error};
pub use policy::{PolicyBound, PolicyRouter};
