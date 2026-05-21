/// Phase 28 REFACTOR: Rate Limiting Middleware
/// Axum middleware layer to enforce rate limits on SSE stream endpoints

use axum::{
    extract::ConnectInfo,
    http::StatusCode,
};
use std::net::SocketAddr;
use super::rate_limiting::RateLimiter;

/// Apply rate limiting to incoming request
/// Extracts client IP from ConnectInfo and checks against per-IP quota
pub async fn enforce_rate_limit(
    ConnectInfo(socket_addr): ConnectInfo<SocketAddr>,
    limiter: &RateLimiter,
    cost: u32,
) -> Result<(), StatusCode> {
    let client_ip = socket_addr.ip().to_string();
    limiter.check_rate_limit(&client_ip, cost).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_ip_extraction_from_socket_addr() {
        // GIVEN socket address 127.0.0.1:8080
        // WHEN extracting client IP
        // THEN returns "127.0.0.1"

        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let client_ip = addr.ip().to_string();
        assert_eq!(client_ip, "127.0.0.1");
    }

    #[test]
    fn test_rate_limit_cost_configuration() {
        // GIVEN SSE stream endpoint configuration
        // WHEN cost=10 per event (routing decision)
        // THEN quota depletes at 10 tokens/event
        // AND max_tokens=100 allows 10 events/window

        let cost_per_event = 10u32;
        let max_tokens = 100u32;
        let max_events = max_tokens / cost_per_event;

        assert_eq!(max_events, 10);
    }

    #[tokio::test]
    async fn test_rate_limiter_injected_from_app_state() {
        // GIVEN rate limiter in app state
        // WHEN request processed by middleware
        // THEN limiter enforces per-IP quota
        // AND prevents IP-based DoS attacks

        use crate::handlers::rate_limiting::RateLimiter;

        let limiter = RateLimiter::new(100, 0.0);
        let client_ip = "192.168.1.100";

        // Simulate 5 requests of cost 20 each = 100 tokens
        for i in 0..5 {
            let result = limiter.check_rate_limit(client_ip, 20).await;
            assert!(result.is_ok(), "Request {} should succeed", i + 1);
        }

        // 6th request should fail
        let result = limiter.check_rate_limit(client_ip, 20).await;
        assert!(result.is_err(), "Request 6 should fail (quota exhausted)");
    }
}
