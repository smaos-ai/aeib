/// Phase 28: Production Deployment Layer
/// Rate Limiting & Connection Management for AG-UI SSE streaming
///
/// RED phase: Tests defined before implementation
/// Enforces: Token bucket rate limiting, connection timeouts, max concurrent streams
use axum::http::StatusCode;
use std::sync::Arc;
use tokio::sync::Mutex;

/// Rate limiter for SSE stream endpoints
/// Tracks per-client token consumption using token bucket algorithm
#[derive(Debug, Clone)]
pub struct RateLimiter {
    max_tokens: u32,
    tokens_per_second: f64,
    clients: Arc<Mutex<std::collections::HashMap<String, ClientQuota>>>,
}

#[derive(Debug, Clone)]
struct ClientQuota {
    tokens: f64,
    last_refill: std::time::Instant,
}

impl RateLimiter {
    pub fn new(max_tokens: u32, tokens_per_second: f64) -> Self {
        RateLimiter {
            max_tokens,
            tokens_per_second,
            clients: Arc::new(Mutex::new(std::collections::HashMap::new())),
        }
    }

    pub async fn check_rate_limit(&self, client_id: &str, cost: u32) -> Result<(), StatusCode> {
        let mut clients = self.clients.lock().await;

        let now = std::time::Instant::now();
        let entry = clients.entry(client_id.to_string()).or_insert(ClientQuota {
            tokens: self.max_tokens as f64,
            last_refill: now,
        });

        let elapsed = now.duration_since(entry.last_refill).as_secs_f64();
        entry.tokens += elapsed * self.tokens_per_second;
        entry.tokens = entry.tokens.min(self.max_tokens as f64);
        entry.last_refill = now;

        if entry.tokens >= cost as f64 {
            entry.tokens -= cost as f64;
            Ok(())
        } else {
            Err(StatusCode::TOO_MANY_REQUESTS)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_rate_limiter_allows_within_quota() {
        // GIVEN rate limiter with max_tokens=100, tokens_per_second=10
        // WHEN client requests with cost=50
        // THEN request succeeds (tokens available)

        let limiter = RateLimiter::new(100, 10.0);
        let result = limiter.check_rate_limit("client1", 50).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_rate_limiter_rejects_over_quota() {
        // GIVEN rate limiter with max_tokens=100, tokens_per_second=10
        // WHEN client requests with cost=150 (exceeds max_tokens)
        // THEN request fails with 429 Too Many Requests

        let limiter = RateLimiter::new(100, 10.0);
        let result = limiter.check_rate_limit("client2", 150).await;
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::TOO_MANY_REQUESTS);
    }

    #[tokio::test]
    async fn test_rate_limiter_depletes_tokens() {
        // GIVEN rate limiter with max_tokens=100
        // WHEN client makes multiple requests (50 + 40 = 90)
        // THEN first two requests succeed, third fails

        let limiter = RateLimiter::new(100, 0.0);

        let r1 = limiter.check_rate_limit("client3", 50).await;
        assert!(r1.is_ok());

        let r2 = limiter.check_rate_limit("client3", 40).await;
        assert!(r2.is_ok());

        let r3 = limiter.check_rate_limit("client3", 20).await;
        assert!(r3.is_err());
    }

    #[tokio::test]
    async fn test_rate_limiter_refills_over_time() {
        // GIVEN rate limiter with max_tokens=100, tokens_per_second=10
        // WHEN client exhausts quota, then waits 0.2s
        // THEN ~2 tokens refilled, but not exceeding max_tokens

        let limiter = RateLimiter::new(100, 10.0);

        // Exhaust quota
        let _ = limiter.check_rate_limit("client4", 100).await;

        // Wait for refill
        tokio::time::sleep(tokio::time::Duration::from_millis(200)).await;

        // Should succeed with ~2 tokens refilled
        let result = limiter.check_rate_limit("client4", 1).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_rate_limiter_isolates_clients() {
        // GIVEN rate limiter with multiple clients
        // WHEN client1 exhausts quota
        // THEN client2 still has full quota (independent quotas)

        let limiter = RateLimiter::new(100, 0.0);

        // Client 1 exhausts quota
        let _ = limiter.check_rate_limit("client5", 100).await;

        // Client 2 should have independent quota
        let result = limiter.check_rate_limit("client6", 100).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_sse_stream_endpoint_enforces_rate_limiting() {
        // GIVEN GET /api/rce/stream with Bearer token
        // WHEN client exceeds rate limit (>100 tokens/window)
        // THEN returns 429 Too Many Requests
        // AND stream is rejected before connection established

        // Placeholder: Rate limiting middleware integration test
        // Will be implemented in GREEN phase with request context
    }

    #[tokio::test]
    async fn test_rate_limiting_respects_client_identity() {
        // GIVEN multiple clients connecting to /api/rce/stream
        // WHEN each client has independent token bucket
        // THEN rate limit is per-client, not global
        // AND does not affect other clients

        // Placeholder: Integration test for multi-client isolation
    }

    #[tokio::test]
    async fn test_connection_timeout_closes_idle_streams() {
        // GIVEN SSE stream connected and idle for >30s
        // WHEN server timeout triggers
        // THEN stream closes gracefully
        // AND resources are freed

        // Placeholder: Connection management test
    }

    #[tokio::test]
    async fn test_max_concurrent_streams_limit() {
        // GIVEN rate limiter with max_concurrent_streams=10
        // WHEN 11th client attempts to connect
        // THEN returns 503 Service Unavailable
        // AND connection rejected before stream established

        // Placeholder: Concurrency management test
    }
}
