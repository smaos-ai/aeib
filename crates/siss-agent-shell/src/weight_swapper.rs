/// Phase 53: Weight Swapper — Hot-Swap with AP2 Mandate Gate + TTFT Verification
/// AP2 gate is fail-closed: no signature → no swap.

use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct AdapterManifest {
    pub adapter_id: Uuid,
    pub adapter_path: String,
    pub ap2_mandate_signature: Option<String>,
    pub training_examples: usize,
    pub base_confidence: f64,
}

pub trait InferenceEndpoint: Send + Sync {
    fn commit_adapter(&self, manifest: &AdapterManifest) -> Result<(), SwapError>;
    fn baseline_ttft_ms(&self) -> u64;
    fn probe_ttft_ms(&self) -> u64;
}

#[derive(Debug, PartialEq, Eq)]
pub enum SwapError {
    MandateMissing,
    TtftExceededBaseline { measured_ms: u64, baseline_ms: u64 },
    EndpointUnreachable,
}

pub struct WeightSwapper<E: InferenceEndpoint> {
    pub endpoint: E,
    pub ttft_margin_pct: f64,
}

impl<E: InferenceEndpoint> WeightSwapper<E> {
    /// Hot-swap new LoRA adapter into the inference endpoint.
    /// RULE A: manifest.ap2_mandate_signature.is_none() → Err(MandateMissing)
    /// RULE B: endpoint.commit_adapter(manifest) → propagate Err(EndpointUnreachable) if fails
    /// RULE C: measured = endpoint.probe_ttft_ms();
    ///         if measured > baseline * (1.0 + ttft_margin_pct) → Err(TtftExceededBaseline)
    /// RULE D: Ok(()) — swap committed and TTFT within bounds
    pub fn swap(&self, manifest: &AdapterManifest) -> Result<(), SwapError> {
        if manifest.ap2_mandate_signature.is_none() {
            return Err(SwapError::MandateMissing);
        }

        self.endpoint.commit_adapter(manifest)?;

        let measured = self.endpoint.probe_ttft_ms();
        let baseline = self.endpoint.baseline_ttft_ms();
        let threshold = (baseline as f64 * (1.0 + self.ttft_margin_pct)) as u64;

        if measured > threshold {
            return Err(SwapError::TtftExceededBaseline {
                measured_ms: measured,
                baseline_ms: baseline,
            });
        }

        Ok(())
    }
}

pub struct MockInferenceEndpoint {
    pub available: bool,
    pub ttft_ms: u64,
    pub baseline_ms: u64,
}

impl InferenceEndpoint for MockInferenceEndpoint {
    fn commit_adapter(&self, _manifest: &AdapterManifest) -> Result<(), SwapError> {
        if self.available {
            Ok(())
        } else {
            Err(SwapError::EndpointUnreachable)
        }
    }

    fn baseline_ttft_ms(&self) -> u64 {
        self.baseline_ms
    }

    fn probe_ttft_ms(&self) -> u64 {
        self.ttft_ms
    }
}
