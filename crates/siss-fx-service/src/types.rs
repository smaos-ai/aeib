use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Currency {
    EUR,
    GBP,
    JPY,
    CNY,
    USD,
}

impl fmt::Display for Currency {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Currency::EUR => "EUR",
                Currency::GBP => "GBP",
                Currency::JPY => "JPY",
                Currency::CNY => "CNY",
                Currency::USD => "USD",
            }
        )
    }
}

impl Currency {
    pub fn from_code(code: &str) -> Option<Self> {
        match code {
            "EUR" => Some(Currency::EUR),
            "GBP" => Some(Currency::GBP),
            "JPY" => Some(Currency::JPY),
            "CNY" => Some(Currency::CNY),
            "USD" => Some(Currency::USD),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FxRate {
    pub from: Currency,
    pub to: Currency,
    pub rate: f64,
    pub fetched_at: DateTime<Utc>,
}

#[derive(Debug, thiserror::Error)]
pub enum FxError {
    #[error("Unsupported currency pair: {from} -> {to}")]
    UnsupportedPair { from: Currency, to: Currency },
    #[error("Provider error: {0}")]
    ProviderError(String),
    #[error("Conversion failed: {0}")]
    ConversionFailed(String),
    #[error("Cache error: {0}")]
    CacheError(String),
}
