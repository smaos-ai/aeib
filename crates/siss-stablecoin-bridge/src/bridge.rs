use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use tokio::sync::RwLock;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum BridgeStatus {
    Healthy,
    Degraded { reason: String },
}

pub struct StablecoinBridge {
    usdc_rate_cents: Arc<RwLock<i64>>,
    circuit_breaker: Arc<AtomicBool>,
}

impl StablecoinBridge {
    pub fn new(initial_rate_cents: i64) -> Self {
        StablecoinBridge {
            usdc_rate_cents: Arc::new(RwLock::new(initial_rate_cents)),
            circuit_breaker: Arc::new(AtomicBool::new(false)),
        }
    }

    pub async fn deposit(&self, amount_cents: i64) -> Result<BridgeStatus, String> {
        if self.circuit_breaker.load(Ordering::SeqCst) {
            return Ok(BridgeStatus::Degraded {
                reason: "Circuit breaker open".to_string(),
            });
        }

        if amount_cents <= 0 {
            return Err("Invalid amount".to_string());
        }

        // Simulate deposit operation
        Ok(BridgeStatus::Healthy)
    }

    pub async fn withdraw(&self, amount_cents: i64) -> Result<BridgeStatus, String> {
        if self.circuit_breaker.load(Ordering::SeqCst) {
            return Ok(BridgeStatus::Degraded {
                reason: "Circuit breaker open".to_string(),
            });
        }

        if amount_cents <= 0 {
            return Err("Invalid amount".to_string());
        }

        Ok(BridgeStatus::Healthy)
    }

    pub async fn get_status(&self) -> BridgeStatus {
        if self.circuit_breaker.load(Ordering::SeqCst) {
            BridgeStatus::Degraded {
                reason: "Circuit breaker open".to_string(),
            }
        } else {
            BridgeStatus::Healthy
        }
    }

    pub fn trigger_circuit_breaker(&self) {
        self.circuit_breaker.store(true, Ordering::SeqCst);
    }

    pub fn reset_circuit_breaker(&self) {
        self.circuit_breaker.store(false, Ordering::SeqCst);
    }

    pub async fn set_usdc_rate(&self, rate_cents: i64) {
        let mut rate = self.usdc_rate_cents.write().await;
        *rate = rate_cents;
    }

    pub async fn get_usdc_rate(&self) -> i64 {
        *self.usdc_rate_cents.read().await
    }
}

impl Clone for StablecoinBridge {
    fn clone(&self) -> Self {
        StablecoinBridge {
            usdc_rate_cents: Arc::clone(&self.usdc_rate_cents),
            circuit_breaker: Arc::clone(&self.circuit_breaker),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_bridge_deposit() {
        let bridge = StablecoinBridge::new(10000);
        let result = bridge.deposit(5000).await.unwrap();
        matches!(result, BridgeStatus::Healthy);
    }

    #[tokio::test]
    async fn test_bridge_circuit_breaker() {
        let bridge = StablecoinBridge::new(10000);
        bridge.trigger_circuit_breaker();

        let status = bridge.get_status().await;
        matches!(status, BridgeStatus::Degraded { .. });
    }

    #[tokio::test]
    async fn test_bridge_rate_updates() {
        let bridge = StablecoinBridge::new(10000);
        bridge.set_usdc_rate(12000).await;

        let rate = bridge.get_usdc_rate().await;
        assert_eq!(rate, 12000);
    }
}
