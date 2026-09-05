use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
/// Double-Buffered LoRA Adapter Swap with Atomic CAS
///
/// Implements zero-KV-cache-flush model evolution by maintaining two LoRA adapters
/// in unified memory and swapping via atomic compare-and-swap (CAS). This ensures
/// < 50ms latency for policy updates without interrupting in-flight requests.
///
/// Memory Model:
/// - Primary adapter: Currently active weights in Rapid-MLX unified memory
/// - Secondary adapter: Staged weights (new Policy Ledger delta) in unified memory
/// - Atomic pointer: Points to primary; CAS swaps to secondary on approval
/// - KV cache: Unchanged; only the projection matrix (LoRA weights) updates
use std::sync::atomic::{AtomicPtr, AtomicU64, Ordering};
use std::sync::Arc;
use uuid::Uuid;

// =====================================================================
// TYPES
// =====================================================================

/// Represents a LoRA adapter in unified memory
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoRAAdapter {
    pub id: Uuid,
    /// Version from Policy Ledger
    pub version: u64,
    /// Bytes allocated in unified memory
    pub memory_bytes: u64,
    /// SHA-256 hash of adapter weights (for integrity)
    pub weights_checksum: String,
    /// Timestamp of deployment
    pub deployed_at: DateTime<Utc>,
}

/// Double-buffered LoRA swap manager
/// Uses atomic pointer to switch between two adapters without allocation/deallocation
pub struct DoubleBufferedSwap {
    /// Primary adapter pointer (currently active)
    primary: Arc<AtomicPtr<LoRAAdapter>>,
    /// Secondary adapter pointer (staged for swap)
    secondary: Arc<AtomicPtr<LoRAAdapter>>,
    /// Swap counter (monotonically increasing for audit trail)
    swap_counter: Arc<AtomicU64>,
    /// Unified memory capacity (bytes)
    unified_memory_bytes: u64,
    /// Swap latency metric (microseconds, for SLA verification)
    last_swap_latency_us: Arc<AtomicU64>,
}

impl DoubleBufferedSwap {
    /// Create a new double-buffered swap manager
    /// `unified_memory_bytes`: Total unified memory available for adapters
    pub fn new(unified_memory_bytes: u64) -> Self {
        Self {
            primary: Arc::new(AtomicPtr::new(std::ptr::null_mut())),
            secondary: Arc::new(AtomicPtr::new(std::ptr::null_mut())),
            swap_counter: Arc::new(AtomicU64::new(0)),
            unified_memory_bytes,
            last_swap_latency_us: Arc::new(AtomicU64::new(0)),
        }
    }

    /// Allocate a new adapter slot in unified memory (returns Box to manage lifetime)
    pub fn allocate_adapter(&self, adapter: LoRAAdapter) -> Result<Box<LoRAAdapter>, String> {
        if adapter.memory_bytes > self.unified_memory_bytes {
            return Err(format!(
                "Adapter too large: {} > {}",
                adapter.memory_bytes, self.unified_memory_bytes
            ));
        }
        Ok(Box::new(adapter))
    }

    /// Get the currently active primary adapter (for inference)
    pub fn get_primary(&self) -> Option<&'static LoRAAdapter> {
        let ptr = self.primary.load(Ordering::Acquire);
        if ptr.is_null() {
            None
        } else {
            unsafe { Some(&*ptr) }
        }
    }

    /// Get the staged secondary adapter (for canary evaluation)
    pub fn get_secondary(&self) -> Option<&'static LoRAAdapter> {
        let ptr = self.secondary.load(Ordering::Acquire);
        if ptr.is_null() {
            None
        } else {
            unsafe { Some(&*ptr) }
        }
    }

    /// Stage a new adapter in the secondary slot (replaces existing secondary)
    pub fn stage_adapter(&self, new_adapter: Box<LoRAAdapter>) -> Result<(), String> {
        let new_ptr = Box::into_raw(new_adapter);
        let old_ptr = self.secondary.swap(new_ptr, Ordering::Release);

        // Drop old secondary if it existed
        if !old_ptr.is_null() {
            unsafe {
                drop(Box::from_raw(old_ptr));
            }
        }

        Ok(())
    }

    /// Atomic swap: primary ← secondary via compare-and-swap
    /// Returns the old primary adapter (caller must drop)
    /// Fail-closed: Returns error if primary doesn't match expected_version
    pub fn swap_primary_atomic(&self, expected_version: u64) -> Result<Box<LoRAAdapter>, String> {
        let start_time = std::time::Instant::now();

        // Verify current primary version matches expected
        let primary_ptr = self.primary.load(Ordering::Acquire);
        if !primary_ptr.is_null() {
            let primary_version = unsafe { (*primary_ptr).version };
            if primary_version != expected_version {
                return Err(format!(
                    "Primary version mismatch: {} != {}",
                    primary_version, expected_version
                ));
            }
        }

        // Load secondary
        let secondary_ptr = self.secondary.load(Ordering::Acquire);
        if secondary_ptr.is_null() {
            return Err("No staged adapter in secondary slot".to_string());
        }

        // Atomic CAS: swap primary to secondary
        let result = self.primary.compare_exchange(
            primary_ptr,
            secondary_ptr,
            Ordering::Release,
            Ordering::Acquire,
        );

        match result {
            Ok(_) => {
                // Success: CAS succeeded, primary now points to secondary
                // Clear secondary slot
                self.secondary
                    .store(std::ptr::null_mut(), Ordering::Release);

                // Record swap latency
                let latency_us = start_time.elapsed().as_micros() as u64;
                self.last_swap_latency_us
                    .store(latency_us, Ordering::Release);

                // Increment swap counter
                self.swap_counter.fetch_add(1, Ordering::Release);

                // Convert old primary back to Box for caller to drop
                if primary_ptr.is_null() {
                    Ok(Box::new(LoRAAdapter {
                        id: Uuid::nil(),
                        version: 0,
                        memory_bytes: 0,
                        weights_checksum: String::new(),
                        deployed_at: Utc::now(),
                    }))
                } else {
                    Ok(unsafe { Box::from_raw(primary_ptr) })
                }
            }
            Err(_) => {
                // CAS failed: primary was modified concurrently (split-brain detected)
                Err("Concurrent primary modification detected (split-brain)".to_string())
            }
        }
    }

    /// Get the current swap counter (for audit trail)
    pub fn swap_counter(&self) -> u64 {
        self.swap_counter.load(Ordering::Acquire)
    }

    /// Get the last swap latency (microseconds)
    pub fn last_swap_latency_us(&self) -> u64 {
        self.last_swap_latency_us.load(Ordering::Acquire)
    }

    /// Check memory pressure: verify we have capacity for the staged adapter
    pub fn check_memory_pressure(&self, enclave_max_utilization: f64) -> Result<(), String> {
        let primary_mem = self.get_primary().map(|a| a.memory_bytes).unwrap_or(0);

        let secondary_mem = self.get_secondary().map(|a| a.memory_bytes).unwrap_or(0);

        let total_used = primary_mem + secondary_mem;
        let max_allowed = (self.unified_memory_bytes as f64 * enclave_max_utilization) as u64;

        if total_used > max_allowed {
            return Err(format!(
                "Memory pressure critical: {}/{} bytes ({:.2}% utilization, max {:.2}%)",
                total_used,
                self.unified_memory_bytes,
                (total_used as f64 / self.unified_memory_bytes as f64) * 100.0,
                enclave_max_utilization * 100.0
            ));
        }

        Ok(())
    }

    /// Get detailed memory stats
    pub fn memory_stats(&self) -> MemoryStats {
        let primary_mem = self.get_primary().map(|a| a.memory_bytes).unwrap_or(0);

        let secondary_mem = self.get_secondary().map(|a| a.memory_bytes).unwrap_or(0);

        let total_used = primary_mem + secondary_mem;
        let utilization = total_used as f64 / self.unified_memory_bytes as f64;

        MemoryStats {
            primary_bytes: primary_mem,
            secondary_bytes: secondary_mem,
            total_used_bytes: total_used,
            total_capacity_bytes: self.unified_memory_bytes,
            utilization_percent: utilization * 100.0,
        }
    }
}

#[async_trait]
impl crate::orchestrator::evolution_gate::DoubleBufferedSwap for DoubleBufferedSwap {
    async fn execute_swap(&self, version: u64) -> Result<()> {
        self.swap_primary_atomic(version)
            .map(|_| ())
            .map_err(|e| anyhow::anyhow!("{}", e))
    }

    async fn discard(&self, _version: u64) -> Result<()> {
        self.secondary
            .store(std::ptr::null_mut(), Ordering::Release);
        Ok(())
    }
}

/// Memory utilization snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryStats {
    pub primary_bytes: u64,
    pub secondary_bytes: u64,
    pub total_used_bytes: u64,
    pub total_capacity_bytes: u64,
    pub utilization_percent: f64,
}

// =====================================================================
// TESTS
// =====================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_allocate_adapter() {
        let swap = DoubleBufferedSwap::new(1024 * 1024); // 1MB

        let adapter = LoRAAdapter {
            id: Uuid::new_v4(),
            version: 1,
            memory_bytes: 512 * 1024,
            weights_checksum: "abc123".to_string(),
            deployed_at: Utc::now(),
        };

        let result = swap.allocate_adapter(adapter);
        assert!(result.is_ok());
    }

    #[test]
    fn test_allocate_oversized_adapter_fails() {
        let swap = DoubleBufferedSwap::new(1024 * 1024); // 1MB

        let adapter = LoRAAdapter {
            id: Uuid::new_v4(),
            version: 1,
            memory_bytes: 2 * 1024 * 1024, // 2MB (too large)
            weights_checksum: "abc123".to_string(),
            deployed_at: Utc::now(),
        };

        let result = swap.allocate_adapter(adapter);
        assert!(result.is_err());
    }

    #[test]
    fn test_stage_and_swap() {
        let swap = DoubleBufferedSwap::new(1024 * 1024);

        // Stage a secondary adapter
        let secondary = LoRAAdapter {
            id: Uuid::new_v4(),
            version: 2,
            memory_bytes: 512 * 1024,
            weights_checksum: "def456".to_string(),
            deployed_at: Utc::now(),
        };

        swap.stage_adapter(Box::new(secondary.clone()))
            .expect("stage");

        assert!(swap.get_secondary().is_some());

        // Swap primary ← secondary (primary is initially null)
        let result = swap.swap_primary_atomic(0);
        assert!(result.is_ok());

        // Secondary should now be primary
        let primary = swap.get_primary().expect("primary exists");
        assert_eq!(primary.version, 2);
    }

    #[test]
    fn test_memory_pressure_check() {
        let swap = DoubleBufferedSwap::new(1024 * 1024); // 1MB

        // Stage a large adapter (800KB)
        let adapter = LoRAAdapter {
            id: Uuid::new_v4(),
            version: 1,
            memory_bytes: 800 * 1024,
            weights_checksum: "xyz789".to_string(),
            deployed_at: Utc::now(),
        };

        swap.stage_adapter(Box::new(adapter)).expect("stage");

        // Check pressure at 0.25 utilization cap (256KB for 1MB)
        let result = swap.check_memory_pressure(0.25);
        assert!(result.is_err(), "Should fail with 800KB staged > 256KB cap");

        // Check at higher cap (0.9 = 920KB available)
        let result = swap.check_memory_pressure(0.9);
        assert!(result.is_ok(), "Should pass at 0.9 utilization cap");
    }

    #[test]
    fn test_swap_counter_increments() {
        let swap = DoubleBufferedSwap::new(1024 * 1024);

        assert_eq!(swap.swap_counter(), 0);

        // Stage and swap
        let adapter = LoRAAdapter {
            id: Uuid::new_v4(),
            version: 1,
            memory_bytes: 512 * 1024,
            weights_checksum: "abc".to_string(),
            deployed_at: Utc::now(),
        };

        swap.stage_adapter(Box::new(adapter)).expect("stage");
        swap.swap_primary_atomic(0).expect("swap");

        assert_eq!(swap.swap_counter(), 1);
    }

    #[test]
    fn test_swap_latency_recorded() {
        let swap = DoubleBufferedSwap::new(1024 * 1024);

        let adapter = LoRAAdapter {
            id: Uuid::new_v4(),
            version: 1,
            memory_bytes: 512 * 1024,
            weights_checksum: "abc".to_string(),
            deployed_at: Utc::now(),
        };

        swap.stage_adapter(Box::new(adapter)).expect("stage");
        swap.swap_primary_atomic(0).expect("swap");

        let latency = swap.last_swap_latency_us();
        assert!(latency < 50_000, "Swap must complete in < 50ms (50000 µs)");
    }
}
