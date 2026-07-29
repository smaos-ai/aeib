// Stream 6: USA Creator KYC/AML Integration Layer
//
// Integrates Know-Your-Customer (KYC) and Anti-Money Laundering (AML) checks
// into Layer 0 governance gate. Before any tool invocation, verifies creator
// identity + compliance status.

pub mod aml_checker;
pub mod error;
pub mod kyc_verifier;
pub mod stream6_gate;

pub use aml_checker::{AMLChecker, AMLRiskLevel, SanctionedEntity};
pub use error::{Stream6Error, Stream6Result};
pub use kyc_verifier::{KYCRecord, KYCStatus, KYCVerifier};
pub use stream6_gate::{ComplianceResult, Stream6Gate};
