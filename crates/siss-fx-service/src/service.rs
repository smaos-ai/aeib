use crate::cache::RateCache;
use crate::provider::RateProvider;
use crate::types::{Currency, FxError, FxRate};
use std::marker::PhantomData;

/// Banker's rounding: round to nearest even
fn bankers_round(value: f64) -> i64 {
    let rounded = value.round();
    if (value - value.floor() - 0.5).abs() < f64::EPSILON {
        // Exactly 0.5, round to nearest even
        if rounded as i64 % 2 == 0 {
            rounded as i64
        } else {
            (rounded - 1.0) as i64
        }
    } else {
        rounded as i64
    }
}

pub struct FxService<P: RateProvider> {
    cache: RateCache,
    provider: P,
    _marker: PhantomData<P>,
}

impl<P: RateProvider> FxService<P> {
    pub fn new(provider: P, cache_staleness_secs: u64) -> Self {
        FxService {
            cache: RateCache::new(cache_staleness_secs),
            provider,
            _marker: PhantomData,
        }
    }

    pub async fn convert(
        &self,
        amount_cents: i64,
        from: Currency,
        to: Currency,
    ) -> Result<i64, FxError> {
        // Same currency short-circuit
        if from == to {
            return Ok(amount_cents);
        }

        let rate = self.cache.get_or_refresh(from, to, &self.provider).await?;

        // Convert: amount_cents -> amount_dollars -> converted_dollars -> converted_cents
        let amount_dollars = amount_cents as f64 / 100.0;
        let converted_dollars = amount_dollars * rate.rate;
        let converted_cents = converted_dollars * 100.0;

        Ok(bankers_round(converted_cents))
    }

    pub async fn get_rate(&self, from: Currency, to: Currency) -> Result<FxRate, FxError> {
        self.cache.get_or_refresh(from, to, &self.provider).await
    }

    pub fn invalidate_cache(&self, from: Currency, to: Currency) {
        self.cache.invalidate(from, to);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provider::MockProvider;

    #[tokio::test]
    async fn test_convert_same_currency() {
        let provider = MockProvider { rate: 1.2 };
        let service = FxService::new(provider, 300);

        let result = service
            .convert(10000, Currency::EUR, Currency::EUR)
            .await
            .unwrap();
        assert_eq!(result, 10000); // No conversion
    }

    #[tokio::test]
    async fn test_convert_with_rate() {
        let provider = MockProvider { rate: 1.2 };
        let service = FxService::new(provider, 300);

        let result = service
            .convert(10000, Currency::EUR, Currency::USD)
            .await
            .unwrap();
        // 100 EUR * 1.2 = 120 USD = 12000 cents
        assert_eq!(result, 12000);
    }

    #[tokio::test]
    async fn test_bankers_rounding() {
        // Test rounding to nearest even
        assert_eq!(bankers_round(1.5), 2); // Round to nearest even
        assert_eq!(bankers_round(2.5), 2); // Round to nearest even
        assert_eq!(bankers_round(3.5), 4); // Round to nearest even
        assert_eq!(bankers_round(1.4), 1);
        assert_eq!(bankers_round(1.6), 2);
    }
}
