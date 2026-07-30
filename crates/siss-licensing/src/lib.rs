pub mod audit_trail;
pub mod key_generation;
pub mod license_model;
pub mod repo;
pub mod stripe_integration;
pub mod types;
pub mod usage_tracking;
pub mod validation;

#[cfg(feature = "axum")]
pub mod handler;

pub use types::{License, LicenseError, LicenseEvent, Sku, VerifiedLicense};
pub use validation::verify_license;
pub use license_model::LicenseEnforcer;
pub use key_generation::LicenseKeyGenerator;
pub use usage_tracking::UsageTracker;
pub use audit_trail::AuditTrail;
