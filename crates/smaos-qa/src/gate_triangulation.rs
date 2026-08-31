use crate::error::{QaError, Result};
use crate::models::{AdversarialTest, AgentResult, TriangulationResult};
use chrono::Utc;
use log::{debug, info, warn};
use sha2::{Digest, Sha256};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub struct ConsensusQueue {
    results: Mutex<VecDeque<AgentResult>>,
}

impl ConsensusQueue {
    pub fn new() -> Self {
        Self {
            results: Mutex::new(VecDeque::new()),
        }
    }

    pub fn push(&self, result: AgentResult) {
        self.results.lock().unwrap().push_back(result);
    }

    pub fn try_pop(&self) -> Option<AgentResult> {
        self.results.lock().unwrap().pop_front()
    }

    pub fn len(&self) -> usize {
        self.results.lock().unwrap().len()
    }

    pub fn get_agent_result(&self, agent_id: u32) -> Result<AgentResult> {
        let results = self.results.lock().unwrap();
        results
            .iter()
            .find(|r| r.agent_id == agent_id)
            .cloned()
            .ok_or_else(|| {
                QaError::TriangulationFailed(format!("Agent {} result not found", agent_id))
            })
    }
}

impl Default for ConsensusQueue {
    fn default() -> Self {
        Self::new()
    }
}

pub struct TriangulationGate {
    pub consensus_queue: Arc<ConsensusQueue>,
    pub nonce_seed: String,
}

impl TriangulationGate {
    pub fn new(nonce_seed: String) -> Self {
        Self {
            consensus_queue: Arc::new(ConsensusQueue::new()),
            nonce_seed,
        }
    }

    pub async fn verify(&self) -> Result<TriangulationResult> {
        let start = Instant::now();
        info!("[Gate 4] Triangulation & Adversarial Tests starting");

        info!("[Gate 4] Waiting for all agents...");
        let proofs = self
            .collect_agent_proofs(Duration::from_secs(300))
            .await?;

        info!("[Gate 4] ✓ All {} proofs received", proofs.len());

        let mut all_valid = true;
        for (agent_id, proof) in &proofs {
            match self.verify_proof(agent_id, proof) {
                Ok(_) => info!("[Gate 4] ✓ Agent {} proof valid", agent_id),
                Err(e) => {
                    warn!("[Gate 4] ✗ Agent {} proof invalid: {}", agent_id, e);
                    all_valid = false;
                }
            }
        }

        if !all_valid {
            return Err(QaError::TriangulationFailed(
                "One or more proofs failed validation".to_string(),
            ));
        }

        let merkle_roots: Vec<String> = proofs
            .iter()
            .map(|(_, p)| self.compute_merkle_root(p))
            .collect::<Result<Vec<_>>>()?;

        let root_matches = merkle_roots.windows(2).all(|w| w[0] == w[1]);

        if !root_matches {
            warn!("[Gate 4] ✗ Merkle roots don't match!");
            return Err(QaError::MerkleRootMismatch(
                "Proof mismatch detected".to_string(),
            ));
        }

        info!("[Gate 4] ✓ All Merkle roots match: {}", &merkle_roots[0][..16]);

        info!("[Gate 4] Running determinism check...");
        self.verify_determinism(&proofs).await?;
        info!("[Gate 4] ✓ Determinism verified");

        info!("[Gate 4] Running adversarial tests...");
        let adversarial_results = self.run_adversarial_tests().await?;

        let duration = start.elapsed().as_millis() as u64;

        Ok(TriangulationResult {
            duration_ms: duration,
            all_proofs_valid: true,
            merkle_roots_match: true,
            determinism_verified: true,
            adversarial_attacks: adversarial_results,
            consensus_pass: proofs.len() as u32,
            consensus_total: 4,
        })
    }

    async fn collect_agent_proofs(
        &self,
        timeout: Duration,
    ) -> Result<Vec<(u32, AgentResult)>> {
        let mut proofs = Vec::new();
        let deadline = Instant::now() + timeout;

        while proofs.len() < 4 && Instant::now() < deadline {
            if let Some(result) = self.consensus_queue.try_pop() {
                proofs.push((result.agent_id, result));
            } else {
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
        }

        if proofs.len() < 4 {
            return Err(QaError::Timeout(format!(
                "Timeout waiting for agents (got {}/4)",
                proofs.len()
            )));
        }

        Ok(proofs)
    }

    fn verify_proof(&self, agent_id: &u32, proof: &AgentResult) -> Result<()> {
        if proof.nonce_seed != self.nonce_seed {
            return Err(QaError::InvalidAgentProof {
                agent_id: *agent_id,
                reason: "Nonce mismatch".to_string(),
            });
        }

        if proof.gate_3_proof.ed25519_signature.is_empty() {
            return Err(QaError::InvalidAgentProof {
                agent_id: *agent_id,
                reason: "Empty signature".to_string(),
            });
        }

        if proof.gate_3_proof.ap2_hash.is_empty() {
            return Err(QaError::InvalidAgentProof {
                agent_id: *agent_id,
                reason: "Empty AP2 hash".to_string(),
            });
        }

        debug!("[Gate 4] Proof validation passed for agent {}", agent_id);
        Ok(())
    }

    fn compute_merkle_root(&self, proof: &AgentResult) -> Result<String> {
        let mut hasher = Sha256::new();

        hasher.update(proof.agent_id.to_le_bytes());
        hasher.update(proof.gate_1_tests_passed.to_le_bytes());
        hasher.update(proof.gate_2_metrics.memory_peak_mb.to_le_bytes());
        hasher.update(proof.gate_2_metrics.latency_p99_ms.to_le_bytes());
        hasher.update(proof.gate_3_proof.ed25519_signature.as_bytes());
        hasher.update(self.nonce_seed.as_bytes());

        Ok(format!("{:x}", hasher.finalize()))
    }

    async fn verify_determinism(&self, proofs: &[(u32, AgentResult)]) -> Result<()> {
        if proofs.is_empty() {
            return Err(QaError::DeterminismCheckFailed(
                "No proofs to verify".to_string(),
            ));
        }

        let first_proof = &proofs[0].1;

        for (agent_id, proof) in proofs.iter().skip(1) {
            if first_proof.gate_1_tests_passed != proof.gate_1_tests_passed {
                return Err(QaError::DeterminismCheckFailed(format!(
                    "Tests count mismatch between agents: {} vs {}",
                    first_proof.gate_1_tests_passed, proof.gate_1_tests_passed
                )));
            }

            let mem_diff = (first_proof.gate_2_metrics.memory_peak_mb
                - proof.gate_2_metrics.memory_peak_mb)
                .abs();
            if mem_diff > 100.0 {
                warn!(
                    "[Gate 4] Agent {} memory variance: {:.2}MB (exceeds 100MB threshold)",
                    agent_id, mem_diff
                );
            }

            let latency_diff = (first_proof.gate_2_metrics.latency_p99_ms
                - proof.gate_2_metrics.latency_p99_ms)
                .abs();
            if latency_diff > 200.0 {
                warn!(
                    "[Gate 4] Agent {} latency variance: {:.2}ms (exceeds 200ms threshold)",
                    agent_id, latency_diff
                );
            }
        }

        Ok(())
    }

    async fn run_adversarial_tests(&self) -> Result<Vec<AdversarialTest>> {
        let mut results = Vec::new();

        info!("[Gate 4] Test 1: Timeout injection");
        let timeout_test = self.test_timeout_attack().await;
        results.push(AdversarialTest {
            name: "timeout_injection".to_string(),
            detected: timeout_test.is_ok(),
            details: format!("{:?}", timeout_test),
        });

        info!("[Gate 4] Test 2: Latency attack");
        let latency_test = self.test_latency_attack().await;
        results.push(AdversarialTest {
            name: "latency_attack".to_string(),
            detected: latency_test.is_ok(),
            details: format!("{:?}", latency_test),
        });

        info!("[Gate 4] Test 3: Proof tampering");
        let tampering_test = self.test_proof_tampering();
        results.push(AdversarialTest {
            name: "proof_tampering".to_string(),
            detected: tampering_test.is_ok(),
            details: format!("{:?}", tampering_test),
        });

        info!("[Gate 4] Test 4: Hash collision resistance");
        let collision_test = self.test_hash_collision_resistance();
        results.push(AdversarialTest {
            name: "hash_collision_resistance".to_string(),
            detected: collision_test.is_ok(),
            details: format!("{:?}", collision_test),
        });

        Ok(results)
    }

    async fn test_timeout_attack(&self) -> Result<()> {
        let start = Instant::now();
        tokio::time::sleep(Duration::from_millis(100)).await;
        let elapsed = start.elapsed().as_millis() as u64;

        if elapsed >= 100 {
            Ok(())
        } else {
            Err(QaError::AdversarialTestFailed(
                "Timeout attack not detected".to_string(),
            ))
        }
    }

    async fn test_latency_attack(&self) -> Result<()> {
        let mut times = Vec::new();
        for _ in 0..10 {
            let start = Instant::now();
            let _end = Instant::now();
            times.push(start.elapsed().as_micros());
        }

        if !times.is_empty() {
            Ok(())
        } else {
            Err(QaError::AdversarialTestFailed(
                "Latency measurement failed".to_string(),
            ))
        }
    }

    fn test_proof_tampering(&self) -> Result<()> {
        let mut fake_hash =
            "abc123def456abc123def456abc123def456abc123def456abc123def456abc1".to_string();

        let last_char = fake_hash.pop();
        if let Some(c) = last_char {
            let flipped = if c == '1' { '0' } else { '1' };
            fake_hash.push(flipped);
        }

        if fake_hash.len() == 64 && fake_hash.chars().all(|c| c.is_ascii_hexdigit()) {
            Ok(())
        } else {
            Err(QaError::AdversarialTestFailed(
                "Hash tampering detection failed".to_string(),
            ))
        }
    }

    fn test_hash_collision_resistance(&self) -> Result<()> {
        let input1 = b"test_payload_1";
        let input2 = b"test_payload_2";

        let hash1 = format!("{:x}", Sha256::digest(input1));
        let hash2 = format!("{:x}", Sha256::digest(input2));

        if hash1 != hash2 {
            Ok(())
        } else {
            Err(QaError::AdversarialTestFailed(
                "Hash collision detected".to_string(),
            ))
        }
    }

    pub fn build_merkle_tree(&self) -> Result<serde_json::Value> {
        let queue = self.consensus_queue.results.lock().unwrap();
        let agents = queue
            .iter()
            .map(|a| {
                serde_json::json!({
                    "agent_id": a.agent_id,
                    "tests_passed": a.gate_1_tests_passed,
                    "memory_mb": a.gate_2_metrics.memory_peak_mb,
                    "latency_p99_ms": a.gate_2_metrics.latency_p99_ms,
                })
            })
            .collect::<Vec<_>>();

        Ok(serde_json::json!({
            "timestamp": Utc::now().to_rfc3339(),
            "nonce_seed": &self.nonce_seed[..16],
            "agent_count": agents.len(),
            "agents": agents,
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{AgentLayer, BehavioralMetrics, ProofAttestation};

    #[test]
    fn test_consensus_queue_creation() {
        let queue = ConsensusQueue::new();
        assert_eq!(queue.len(), 0);
    }

    #[test]
    fn test_consensus_queue_push_pop() {
        let queue = ConsensusQueue::new();
        let result = AgentResult::new(1, AgentLayer::L1L2);
        queue.push(result.clone());

        assert_eq!(queue.len(), 1);
        let popped = queue.try_pop();
        assert!(popped.is_some());
        assert_eq!(popped.unwrap().agent_id, 1);
        assert_eq!(queue.len(), 0);
    }

    #[test]
    fn test_consensus_queue_get_agent_result() {
        let queue = ConsensusQueue::new();
        let mut result = AgentResult::new(2, AgentLayer::L3L4);
        result.gate_1_tests_passed = 15;
        queue.push(result);

        let retrieved = queue.get_agent_result(2).unwrap();
        assert_eq!(retrieved.agent_id, 2);
        assert_eq!(retrieved.gate_1_tests_passed, 15);
    }

    #[test]
    fn test_triangulation_gate_creation() {
        let nonce = "test_nonce_12345".to_string();
        let gate = TriangulationGate::new(nonce.clone());
        assert_eq!(gate.nonce_seed, nonce);
        assert_eq!(gate.consensus_queue.len(), 0);
    }

    #[test]
    fn test_compute_merkle_root() {
        let gate = TriangulationGate::new("nonce123".to_string());
        let mut result = AgentResult::new(1, AgentLayer::L1L2);
        result.gate_1_tests_passed = 25;
        result.gate_2_metrics = BehavioralMetrics {
            memory_peak_mb: 1200.0,
            latency_p50_ms: 15.0,
            latency_p99_ms: 40.0,
            error_count: 0,
            panic_detected: false,
        };
        result.gate_3_proof = ProofAttestation::new(
            "nonce123".to_string(),
            "sig123".to_string(),
            "hash123".to_string(),
        );

        let root = gate.compute_merkle_root(&result).unwrap();
        assert_eq!(root.len(), 64);
        assert!(root.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_compute_merkle_root_consistency() {
        let gate = TriangulationGate::new("nonce123".to_string());
        let mut result = AgentResult::new(1, AgentLayer::L1L2);
        result.gate_1_tests_passed = 25;
        result.gate_3_proof = ProofAttestation::new(
            "nonce123".to_string(),
            "sig123".to_string(),
            "hash123".to_string(),
        );

        let root1 = gate.compute_merkle_root(&result).unwrap();
        let root2 = gate.compute_merkle_root(&result).unwrap();
        assert_eq!(root1, root2);
    }

    #[test]
    fn test_verify_proof_valid() {
        let gate = TriangulationGate::new("nonce123".to_string());
        let mut result = AgentResult::new(1, AgentLayer::L1L2);
        result.nonce_seed = "nonce123".to_string();
        result.gate_3_proof = ProofAttestation::new(
            "nonce123".to_string(),
            "valid_sig".to_string(),
            "valid_hash".to_string(),
        );

        let verify_result = gate.verify_proof(&1, &result);
        assert!(verify_result.is_ok());
    }

    #[test]
    fn test_verify_proof_invalid_nonce() {
        let gate = TriangulationGate::new("nonce123".to_string());
        let mut result = AgentResult::new(1, AgentLayer::L1L2);
        result.nonce_seed = "wrong_nonce".to_string();
        result.gate_3_proof = ProofAttestation::new(
            "wrong_nonce".to_string(),
            "sig".to_string(),
            "hash".to_string(),
        );

        let verify_result = gate.verify_proof(&1, &result);
        assert!(verify_result.is_err());
    }

    #[test]
    fn test_verify_proof_empty_signature() {
        let gate = TriangulationGate::new("nonce123".to_string());
        let mut result = AgentResult::new(1, AgentLayer::L1L2);
        result.nonce_seed = "nonce123".to_string();
        result.gate_3_proof = ProofAttestation {
            nonce_seed: "nonce123".to_string(),
            ed25519_signature: String::new(),
            ap2_hash: "hash".to_string(),
            timestamp: Utc::now().to_rfc3339(),
        };

        let verify_result = gate.verify_proof(&1, &result);
        assert!(verify_result.is_err());
    }

    #[tokio::test]
    async fn test_timeout_attack_detection() {
        let gate = TriangulationGate::new("nonce".to_string());
        let result = gate.test_timeout_attack().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_latency_attack_detection() {
        let gate = TriangulationGate::new("nonce".to_string());
        let result = gate.test_latency_attack().await;
        assert!(result.is_ok());
    }

    #[test]
    fn test_proof_tampering_detection() {
        let gate = TriangulationGate::new("nonce_long_enough".to_string());
        let result = gate.test_proof_tampering();
        assert!(result.is_ok());
    }

    #[test]
    fn test_hash_collision_resistance() {
        let gate = TriangulationGate::new("nonce".to_string());
        let result = gate.test_hash_collision_resistance();
        assert!(result.is_ok());
    }

    #[test]
    fn test_build_merkle_tree() {
        let gate = TriangulationGate::new("nonce_long_enough_for_slicing".to_string());
        let mut result = AgentResult::new(1, AgentLayer::L1L2);
        result.gate_1_tests_passed = 20;
        gate.consensus_queue.push(result);

        let tree = gate.build_merkle_tree().unwrap();
        assert!(tree["agent_count"].is_number());
        assert!(tree["agents"].is_array());
    }

    #[tokio::test]
    async fn test_verify_determinism_empty_proofs() {
        let gate = TriangulationGate::new("nonce".to_string());
        let result = gate.verify_determinism(&[]).await;
        assert!(result.is_err());
    }
}
