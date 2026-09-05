pub mod compliance;
pub mod localization;
pub mod payments;

#[cfg(test)]
mod tests;

pub use compliance::*;
pub use localization::*;
pub use payments::*;

#[derive(Debug, Clone)]
pub enum ApacError {
    LocalizationError(String),
    PaymentError(String),
    ComplianceError(String),
}

impl std::fmt::Display for ApacError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ApacError::LocalizationError(msg) => write!(f, "Localization error: {}", msg),
            ApacError::PaymentError(msg) => write!(f, "Payment error: {}", msg),
            ApacError::ComplianceError(msg) => write!(f, "Compliance error: {}", msg),
        }
    }
}

impl std::error::Error for ApacError {}

pub type Result<T> = std::result::Result<T, ApacError>;
