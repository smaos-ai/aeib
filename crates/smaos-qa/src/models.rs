use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AgentLayer {
    L1L2,
    L3L4,
    L5L6,
    L7L8,
}

impl fmt::Display for AgentLayer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AgentLayer::L1L2 => write!(f, "L1L2 (Reasoning)"),
            AgentLayer::L3L4 => write!(f, "L3L4 (Enforcement)"),
            AgentLayer::L5L6 => write!(f, "L5L6 (Orchestration)"),
            AgentLayer::L7L8 => write!(f, "L7L8 (Proof/RAGAS)"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BehavioralMetrics {
    pub memory_peak_mb: f64,
    pub latency_p50_ms: f64,
    pub latency_p99_ms: f64,
    pub error_count: u32,
    pub panic_detected: bool,
}

impl BehavioralMetrics {
    pub fn new() -> Self {
        Self {
            memory_peak_mb: 0.0,
            latency_p50_ms: 0.0,
            latency_p99_ms: 0.0,
            error_count: 0,
            panic_detected: false,
        }
    }
}

impl Default for BehavioralMetrics {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofAttestation {
    pub nonce_seed: String,
    pub ed25519_signature: String,
    pub ap2_hash: String,
    pub timestamp: String,
}

impl ProofAttestation {
    pub fn new(nonce_seed: String, ed25519_signature: String, ap2_hash: String) -> Self {
        Self {
            nonce_seed,
            ed25519_signature,
            ap2_hash,
            timestamp: chrono::Utc::now().to_rfc3339(),
        }
    }
}

impl Default for ProofAttestation {
    fn default() -> Self {
        Self {
            nonce_seed: String::new(),
            ed25519_signature: String::new(),
            ap2_hash: String::new(),
            timestamp: chrono::Utc::now().to_rfc3339(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentResult {
    pub agent_id: u32,
    pub layers: AgentLayer,
    pub gate_1_tests_passed: u32,
    pub gate_2_metrics: BehavioralMetrics,
    pub gate_3_proof: ProofAttestation,
    pub nonce_seed: String,
    pub total_duration_ms: u64,
}

impl AgentResult {
    pub fn new(agent_id: u32, layers: AgentLayer) -> Self {
        Self {
            agent_id,
            layers,
            gate_1_tests_passed: 0,
            gate_2_metrics: BehavioralMetrics::new(),
            gate_3_proof: ProofAttestation::default(),
            nonce_seed: String::new(),
            total_duration_ms: 0,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AdversarialTest {
    pub name: String,
    pub detected: bool,
    pub details: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriangulationResult {
    pub duration_ms: u64,
    pub all_proofs_valid: bool,
    pub merkle_roots_match: bool,
    pub determinism_verified: bool,
    pub adversarial_attacks: Vec<AdversarialTest>,
    pub consensus_pass: u32,
    pub consensus_total: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReadinessState {
    Ready,
    Failed,
    Degraded,
}

impl fmt::Display for ReadinessState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ReadinessState::Ready => write!(f, "Ready"),
            ReadinessState::Failed => write!(f, "Failed"),
            ReadinessState::Degraded => write!(f, "Degraded"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadinessReport {
    pub root_hash: String,
    pub signature: String,
    pub duration_ms: u64,
    pub consensus: String,
    pub readiness_state: ReadinessState,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnitTestResult {
    pub tests_passed: u32,
    pub tests_failed: u32,
    pub panic_log: Vec<String>,
}

impl UnitTestResult {
    pub fn new() -> Self {
        Self {
            tests_passed: 0,
            tests_failed: 0,
            panic_log: Vec::new(),
        }
    }
}

impl Default for UnitTestResult {
    fn default() -> Self {
        Self::new()
    }
}
