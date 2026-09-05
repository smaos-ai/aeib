use crate::{JetsonTarget, QuantizationConfig};

/// Hardware emulation layer for Jetson Thor (with M3 Pro fallback)
pub struct HardwareEmulator {
    target: JetsonTarget,
    // M3 Pro baseline: 39.3 tokens/sec on M3 Pro
    m3_baseline_tokens_per_sec: f64,
}

impl HardwareEmulator {
    /// Create new hardware emulator
    pub fn new(target: JetsonTarget) -> Self {
        Self {
            target,
            m3_baseline_tokens_per_sec: 39.3,
        }
    }

    /// Get target reference
    pub fn target(&self) -> &JetsonTarget {
        &self.target
    }

    /// Get quantization configuration
    pub fn quantization_config(&self) -> QuantizationConfig {
        self.target.quantization_config()
    }

    /// Benchmark inference latency for context size
    ///
    /// Scales from M3 Pro baseline (39.3 tok/s) accounting for:
    /// - Context window size (attention complexity)
    /// - Available memory (KV cache efficiency)
    /// - Quantization impact (FP4 faster than full)
    pub fn benchmark_inference_latency(&self, context_tokens: usize) -> f64 {
        self.benchmark_inference_latency_with_quantization(context_tokens, "full")
    }

    /// Benchmark with specific quantization
    pub fn benchmark_inference_latency_with_quantization(
        &self,
        context_tokens: usize,
        quantization: &str,
    ) -> f64 {
        // Prefill latency model (parallel processing of context)
        // M3 Pro baseline: 39.3 tokens/sec throughput
        // Estimate prefill: ~400 tokens/ms on M3 (batched attention)
        // Jetson Thor: 72 TFLOPS / 20 TFLOPS (M3 equiv) = 3.6x faster
        // So: ~1400 tokens/ms on Jetson

        let m3_prefill_throughput_per_ms = 400.0; // tokens/ms
        let jetson_prefill_throughput_per_ms = 1400.0; // tokens/ms (3.6x faster)

        // Base prefill latency (ms)
        let m3_latency_ms = context_tokens as f64 / m3_prefill_throughput_per_ms;
        let jetson_latency_ms = context_tokens as f64 / jetson_prefill_throughput_per_ms;

        // Context scaling factor (attention complexity increases with context)
        // Linear scaling for kernel-fused attention
        let context_scale = 1.0 + (context_tokens as f64 / 1_000_000.0) * 0.5;

        // Blend between M3 and Jetson estimates
        let blend_factor = if self.target.available {
            1.0 // Use Jetson estimate
        } else {
            0.0 // Use M3 Pro estimate
        };

        let base_latency = m3_latency_ms * (1.0 - blend_factor) + jetson_latency_ms * blend_factor;
        let scaled_latency = base_latency * context_scale;

        // Quantization benefit
        let quant_factor = match quantization {
            "fp4" => 0.8,  // 20% faster
            "int8" => 0.9, // 10% faster
            "bfloat16" => 0.95, // 5% faster
            _ => 1.0, // full precision
        };

        let final_latency = scaled_latency * quant_factor;

        final_latency
    }

    /// Get thermal status (emulated)
    pub fn thermal_status(&self) -> String {
        if !self.target.available {
            "Emulated - Normal".to_string()
        } else {
            "Jetson Thor - Normal".to_string()
        }
    }
}

impl Clone for HardwareEmulator {
    fn clone(&self) -> Self {
        Self {
            target: self.target.clone(),
            m3_baseline_tokens_per_sec: self.m3_baseline_tokens_per_sec,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_emulator_creation() {
        let target = JetsonTarget::jetson_thor_or_emulated();
        let emulator = HardwareEmulator::new(target);
        assert_eq!(emulator.target().memory_gb, 128);
    }

    #[test]
    fn test_latency_scaling() {
        let target = JetsonTarget::jetson_thor_or_emulated();
        let emulator = HardwareEmulator::new(target);

        let lat1 = emulator.benchmark_inference_latency(1_000);
        let lat10 = emulator.benchmark_inference_latency(10_000);
        let lat100 = emulator.benchmark_inference_latency(100_000);

        assert!(lat1 < lat10);
        assert!(lat10 < lat100);
    }
}
