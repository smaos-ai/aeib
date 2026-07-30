use crate::provider::RateProvider;
use crate::types::{Currency, FxError, FxRate};
use dashmap::DashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};

/// RateCache with 300s staleness check (5 minutes)
pub struct RateCache {
    cache: Arc<DashMap<(Currency, Currency), (FxRate, Instant)>>,
    staleness_duration: Duration,
}

impl RateCache {
    pub fn new(staleness_secs: u64) -> Self {
        RateCache {
            cache: Arc::new(DashMap::new()),
            staleness_duration: Duration::from_secs(staleness_secs),
        }
    }

    pub fn default_5_min() -> Self {
        RateCache::new(300)
    }

    pub async fn get_or_refresh<P: RateProvider>(
        &self,
        from: Currency,
        to: Currency,
        provider: &P,
    ) -> Result<FxRate, FxError> {
        let key = (from, to);

        // Check if we have a fresh cached rate
        if let Some(entry) = self.cache.get(&key) {
            let (rate, cached_at) = entry.value();
            if cached_at.elapsed() < self.staleness_duration {
                return Ok(rate.clone());
            }
        }

        // Fetch fresh rate from provider
        let rate = provider.get_rate(from, to).await?;
        self.cache.insert(key, (rate.clone(), Instant::now()));
        Ok(rate)
    }

    pub fn invalidate(&self, from: Currency, to: Currency) {
        self.cache.remove(&(from, to));
    }

    pub fn clear(&self) {
        self.cache.clear();
    }

    pub fn len(&self) -> usize {
        self.cache.len()
    }

    pub fn is_empty(&self) -> bool {
        self.cache.is_empty()
    }
}

impl Clone for RateCache {
    fn clone(&self) -> Self {
        RateCache {
            cache: Arc::clone(&self.cache),
            staleness_duration: self.staleness_duration,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provider::MockProvider;

    #[tokio::test]
    async fn test_cache_stores_and_retrieves() {
        let cache = RateCache::default_5_min();
        let provider = MockProvider { rate: 1.2 };

        let rate1 = cache
            .get_or_refresh(Currency::EUR, Currency::USD, &provider)
            .await
            .unwrap();
        assert_eq!(rate1.rate, 1.2);

        let rate2 = cache
            .get_or_refresh(Currency::EUR, Currency::USD, &provider)
            .await
            .unwrap();
        assert_eq!(rate2.rate, 1.2);
    }

    #[tokio::test]
    async fn test_cache_staleness() {
        let cache = RateCache::new(1); // 1 second staleness
        let provider = MockProvider { rate: 1.2 };

        cache
            .get_or_refresh(Currency::EUR, Currency::USD, &provider)
            .await
            .unwrap();

        // Wait for staleness
        tokio::time::sleep(Duration::from_millis(1100)).await;

        // Should refresh
        let rate = cache
            .get_or_refresh(Currency::EUR, Currency::USD, &provider)
            .await
            .unwrap();
        assert_eq!(rate.rate, 1.2);
    }

    #[tokio::test]
    async fn test_cache_clear() {
        let cache = RateCache::default_5_min();
        let provider = MockProvider { rate: 1.2 };

        cache
            .get_or_refresh(Currency::EUR, Currency::USD, &provider)
            .await
            .unwrap();
        assert_eq!(cache.len(), 1);

        cache.clear();
        assert!(cache.is_empty());
    }
}
