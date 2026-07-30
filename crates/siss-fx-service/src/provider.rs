use crate::types::{Currency, FxRate, FxError};
use chrono::Utc;
use serde::Deserialize;

#[async_trait::async_trait]
pub trait RateProvider: Send + Sync {
    async fn get_rate(&self, from: Currency, to: Currency) -> Result<FxRate, FxError>;
}

pub struct EcbRateProvider {
    client: reqwest::Client,
}

impl EcbRateProvider {
    pub fn new() -> Self {
        EcbRateProvider {
            client: reqwest::Client::new(),
        }
    }
}

impl Default for EcbRateProvider {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Deserialize)]
struct EcbResponse {
    rates: std::collections::HashMap<String, f64>,
}

#[async_trait::async_trait]
impl RateProvider for EcbRateProvider {
    async fn get_rate(&self, from: Currency, to: Currency) -> Result<FxRate, FxError> {
        // If same currency, return rate of 1.0
        if from == to {
            return Ok(FxRate {
                from,
                to,
                rate: 1.0,
                fetched_at: Utc::now(),
            });
        }

        // ECB provides rates relative to EUR
        let base = match from {
            Currency::EUR => "EUR",
            Currency::GBP => "GBP",
            Currency::JPY => "JPY",
            Currency::CNY => "CNY",
            Currency::USD => "USD",
        };

        let target = match to {
            Currency::EUR => "EUR",
            Currency::GBP => "GBP",
            Currency::JPY => "JPY",
            Currency::CNY => "CNY",
            Currency::USD => "USD",
        };

        let url = format!(
            "https://api.exchangerate-api.com/v4/latest/{}",
            base
        );

        let response = self
            .client
            .get(&url)
            .send()
            .await
            .map_err(|e| FxError::ProviderError(e.to_string()))?;

        let body: serde_json::Value = response
            .json()
            .await
            .map_err(|e| FxError::ProviderError(e.to_string()))?;

        let rate = body
            .get("rates")
            .and_then(|rates| rates.get(target))
            .and_then(|r| r.as_f64())
            .ok_or(FxError::UnsupportedPair { from, to })?;

        Ok(FxRate {
            from,
            to,
            rate,
            fetched_at: Utc::now(),
        })
    }
}

/// MockProvider for testing
pub struct MockProvider {
    pub rate: f64,
}

#[async_trait::async_trait]
impl RateProvider for MockProvider {
    async fn get_rate(&self, from: Currency, to: Currency) -> Result<FxRate, FxError> {
        Ok(FxRate {
            from,
            to,
            rate: self.rate,
            fetched_at: Utc::now(),
        })
    }
}
