//! L1: Policy-bound reasoning with EU AI Act enforcement
//! Ensures Claude decisions cite and respect Article 50 + Annex III/I requirements

pub mod error;
pub mod policy;

pub use error::{L1AuditEntry, L1Error};
pub use policy::{PolicyBound, PolicyRouter};
