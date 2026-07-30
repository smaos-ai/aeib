pub mod cache;
pub mod provider;
pub mod service;
pub mod types;

pub use service::FxService;

#[cfg(test)]
mod tests {
    use crate::provider::MockProvider;
    use crate::service::FxService;
    use crate::types::Currency;

    #[tokio::test]
    async fn test_fx_accurate_eur_to_usd() {
        // TODO: Verify EUR->USD conversion within 0.01% of live rate
        // Will fetch from ECB API and validate accuracy
    }

    #[tokio::test]
    async fn test_fx_cache_hit() {
        // TODO: Fetch rate twice, verify second call hits cache
        // Assert cache hit via metrics or timing
    }

    #[tokio::test]
    async fn test_fx_cache_stale_refresh() {
        // TODO: Wait 301s, verify cache refreshes
        // Check staleness threshold (300s = 5 minutes)
    }

    #[tokio::test]
    async fn test_fx_unsupported_pair() {
        // TODO: Request unsupported currency pair, verify error
    }

    #[tokio::test]
    async fn test_fx_identity_same_currency() {
        // TODO: Convert EUR to EUR, verify no conversion (short-circuit)
    }

    #[tokio::test]
    async fn test_concurrent_fx_requests() {
        // TODO: 10 concurrent FX requests, verify no race conditions
    }
}
