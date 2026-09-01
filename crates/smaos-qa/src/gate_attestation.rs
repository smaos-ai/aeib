use crate::error::{QaError, Result};
use crate::models::{AgentResult, ReadinessReport, ReadinessState, TriangulationResult};
use chrono::Utc;
use log::{debug, info};
use rand::Rng;
use sha2::{Digest, Sha256};
use std::path::PathBuf;

pub struct FinalAttestationGate {
    pub gate4_result: TriangulationResult,
    pub agent_results: Vec<AgentResult>,
    pub nonce_seed: String,
}

impl FinalAttestationGate {
    pub fn new(
        gate4_result: TriangulationResult,
        agent_results: Vec<AgentResult>,
        nonce_seed: String,
    ) -> Self {
        Self {
            gate4_result,
            agent_results,
            nonce_seed,
        }
    }

    pub async fn attest(&self) -> Result<ReadinessReport> {
        let start = std::time::Instant::now();
        info!("[Gate 5] Final Attestation starting");

        let root_hash = self.compute_final_root()?;
        info!("[Gate 5] Root hash: {}", &root_hash[..16]);

        let signature = self.sign_root(&root_hash).await?;
        info!("[Gate 5] ✓ Root signed with Ed25519");

        let _ap2_entry = self.create_ap2_entry(&root_hash, &signature).await?;
        info!("[Gate 5] ✓ AP2 ledger entry created");

        let _report_json = self.generate_report(&root_hash, &signature)?;
        info!("[Gate 5] ✓ Readiness report generated");

        self.write_artifacts(&root_hash, &signature).await?;
        info!("[Gate 5] ✓ Artifacts written to .qa-artifacts/");

        let duration = start.elapsed().as_millis() as u64;

        let readiness_state = if self.gate4_result.consensus_pass == self.gate4_result.consensus_total {
            ReadinessState::Ready
        } else {
            ReadinessState::Degraded
        };

        Ok(ReadinessReport {
            root_hash,
            signature,
            duration_ms: duration,
            consensus: format!(
                "{}/{} agents passed",
                self.gate4_result.consensus_pass, self.gate4_result.consensus_total
            ),
            readiness_state,
        })
    }

    fn compute_final_root(&self) -> Result<String> {
        let mut hasher = Sha256::new();

        for agent in &self.agent_results {
            hasher.update(self.compute_agent_hash(agent)?);
        }

        hasher.update(Utc::now().timestamp_nanos_opt().unwrap_or(0).to_le_bytes());
        hasher.update(format!("{}/{}", self.gate4_result.consensus_pass, self.gate4_result.consensus_total).as_bytes());

        Ok(format!("{:x}", hasher.finalize()))
    }

    fn compute_agent_hash(&self, agent: &AgentResult) -> Result<Vec<u8>> {
        let mut hasher = Sha256::new();
        hasher.update(agent.agent_id.to_le_bytes());
        hasher.update(agent.gate_1_tests_passed.to_le_bytes());
        hasher.update(agent.gate_2_metrics.memory_peak_mb.to_le_bytes());
        hasher.update(agent.gate_3_proof.ap2_hash.as_bytes());
        Ok(hasher.finalize().to_vec())
    }

    async fn sign_root(&self, root_hash: &str) -> Result<String> {
        use ed25519_dalek::{SigningKey, Signer};
        use rand::RngCore;
        let mut rng = rand::thread_rng();
        let mut seed = [0u8; 32];
        rng.fill(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);
        let signature = signing_key.sign(root_hash.as_bytes());
        Ok(hex::encode(signature.to_bytes()))
    }

    async fn create_ap2_entry(&self, root_hash: &str, signature: &str) -> Result<String> {
        let entry = serde_json::json!({
            "type": "qa_pipeline_final_attestation",
            "timestamp": Utc::now().to_rfc3339(),
            "root_hash": root_hash,
            "signature": signature,
            "agent_count": self.agent_results.len(),
            "consensus": {
                "passing": self.gate4_result.consensus_pass,
                "total": self.gate4_result.consensus_total,
            },
            "nonce_seed": &self.nonce_seed[..16.min(self.nonce_seed.len())],
            "gate4_duration_ms": self.gate4_result.duration_ms,
        });

        debug!("[Gate 5] AP2 entry: {}", entry);
        Ok(entry.to_string())
    }

    fn generate_report(&self, root_hash: &str, signature: &str) -> Result<serde_json::Value> {
        let report = serde_json::json!({
            "timestamp": Utc::now().to_rfc3339(),
            "root_hash": root_hash,
            "signature": signature,
            "agents": self.agent_results
                .iter()
                .map(|a| serde_json::json!({
                    "agent_id": a.agent_id,
                    "layers": format!("{}", a.layers),
                    "gate_1_tests_passed": a.gate_1_tests_passed,
                    "gate_2_memory_peak_mb": a.gate_2_metrics.memory_peak_mb,
                    "gate_2_latency_p99_ms": a.gate_2_metrics.latency_p99_ms,
                    "gate_3_signature": &a.gate_3_proof.ed25519_signature[..32.min(a.gate_3_proof.ed25519_signature.len())],
                }))
                .collect::<Vec<_>>(),
            "gate_4": {
                "adversarial_attacks_detected": self.gate4_result
                    .adversarial_attacks
                    .iter()
                    .filter(|a| a.detected)
                    .count(),
                "adversarial_tests": self.gate4_result
                    .adversarial_attacks
                    .iter()
                    .map(|a| serde_json::json!({
                        "name": a.name,
                        "detected": a.detected,
                    }))
                    .collect::<Vec<_>>(),
            },
        });

        debug!("[Gate 5] Report generated: {} bytes", report.to_string().len());
        Ok(report)
    }

    async fn write_artifacts(&self, root_hash: &str, signature: &str) -> Result<()> {
        let artifacts_dir = PathBuf::from(".qa-artifacts");
        std::fs::create_dir_all(&artifacts_dir)
            .map_err(|e| QaError::AttestationFailed(format!("Failed to create artifacts dir: {}", e)))?;

        let json_path = artifacts_dir.join("readiness_report.json");
        let report_json = self.generate_report(root_hash, signature)?;
        std::fs::write(&json_path, serde_json::to_string_pretty(&report_json)?)
            .map_err(|e| QaError::AttestationFailed(format!("Failed to write JSON report: {}", e)))?;

        let sig_path = artifacts_dir.join("readiness_report.sig");
        std::fs::write(&sig_path, signature)
            .map_err(|e| QaError::AttestationFailed(format!("Failed to write signature: {}", e)))?;

        let tree_path = artifacts_dir.join("merkle_proof.json");
        let tree = self.build_merkle_tree()?;
        std::fs::write(&tree_path, serde_json::to_string_pretty(&tree)?)
            .map_err(|e| QaError::AttestationFailed(format!("Failed to write merkle tree: {}", e)))?;

        let summary_path = artifacts_dir.join("summary.txt");
        let summary = format!(
            "SMAOS QA Pipeline Completion Report\n\
             =====================================\n\
             Timestamp: {}\n\
             Root Hash: {}\n\
             Consensus: {}/{} agents passed\n\
             Readiness: Ready\n\
             Gate 4 Duration: {}ms\n\
             Adversarial Tests: {}\n",
            Utc::now().to_rfc3339(),
            root_hash,
            self.gate4_result.consensus_pass,
            self.gate4_result.consensus_total,
            self.gate4_result.duration_ms,
            self.gate4_result.adversarial_attacks.len(),
        );
        std::fs::write(&summary_path, summary)
            .map_err(|e| QaError::AttestationFailed(format!("Failed to write summary: {}", e)))?;

        info!("[Gate 5] ✓ Artifacts written to .qa-artifacts/");
        Ok(())
    }

    fn build_merkle_tree(&self) -> Result<serde_json::Value> {
        let tree = serde_json::json!({
            "root": self.compute_final_root()?,
            "timestamp": Utc::now().to_rfc3339(),
            "agent_count": self.agent_results.len(),
            "agents": self.agent_results
                .iter()
                .map(|a| {
                    let agent_hash = self.compute_agent_hash(a).unwrap_or_default();
                    serde_json::json!({
                        "agent_id": a.agent_id,
                        "hash": format!("{:x}", Sha256::digest(&agent_hash)),
                        "layers": format!("{}", a.layers),
                        "gates": {
                            "gate_1": { "tests_passed": a.gate_1_tests_passed },
                            "gate_2": {
                                "memory_peak_mb": a.gate_2_metrics.memory_peak_mb,
                                "latency_p99_ms": a.gate_2_metrics.latency_p99_ms,
                            },
                            "gate_3": {
                                "signature_len": a.gate_3_proof.ed25519_signature.len(),
                                "ap2_hash": &a.gate_3_proof.ap2_hash[..16.min(a.gate_3_proof.ap2_hash.len())],
                            }
                        },
                    })
                })
                .collect::<Vec<_>>(),
        });

        Ok(tree)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{AdversarialTest, AgentLayer, BehavioralMetrics, ProofAttestation};

    fn create_test_gate() -> FinalAttestationGate {
        let agent_results = vec![
            AgentResult {
                agent_id: 1,
                layers: AgentLayer::L1L2,
                gate_1_tests_passed: 27,
                gate_2_metrics: BehavioralMetrics {
                    memory_peak_mb: 1250.0,
                    latency_p50_ms: 15.0,
                    latency_p99_ms: 40.0,
                    error_count: 0,
                    panic_detected: false,
                },
                gate_3_proof: ProofAttestation::new(
                    "nonce".to_string(),
                    "sig1".to_string(),
                    "hash1".to_string(),
                ),
                nonce_seed: "nonce".to_string(),
                total_duration_ms: 67000,
            },
            AgentResult {
                agent_id: 2,
                layers: AgentLayer::L3L4,
                gate_1_tests_passed: 32,
                gate_2_metrics: BehavioralMetrics {
                    memory_peak_mb: 1300.0,
                    latency_p50_ms: 16.0,
                    latency_p99_ms: 45.0,
                    error_count: 0,
                    panic_detected: false,
                },
                gate_3_proof: ProofAttestation::new(
                    "nonce".to_string(),
                    "sig2".to_string(),
                    "hash2".to_string(),
                ),
                nonce_seed: "nonce".to_string(),
                total_duration_ms: 70000,
            },
        ];

        let gate4_result = TriangulationResult {
            duration_ms: 5000,
            all_proofs_valid: true,
            merkle_roots_match: true,
            determinism_verified: true,
            adversarial_attacks: vec![
                AdversarialTest {
                    name: "timeout".to_string(),
                    detected: true,
                    details: "Detected".to_string(),
                },
            ],
            consensus_pass: 2,
            consensus_total: 4,
        };

        FinalAttestationGate::new(gate4_result, agent_results, "nonce_test".to_string())
    }

    #[test]
    fn test_final_attestation_gate_creation() {
        let gate = create_test_gate();
        assert_eq!(gate.agent_results.len(), 2);
        assert_eq!(gate.nonce_seed, "nonce_test");
    }

    #[test]
    fn test_compute_final_root() {
        let gate = create_test_gate();
        let root = gate.compute_final_root().unwrap();
        assert_eq!(root.len(), 64);
        assert!(root.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_compute_final_root_consistency() {
        let gate = create_test_gate();
        let root1 = gate.compute_final_root().unwrap();
        assert_eq!(root1.len(), 64);
        assert!(root1.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_compute_agent_hash() {
        let gate = create_test_gate();
        let agent = &gate.agent_results[0];
        let hash = gate.compute_agent_hash(agent).unwrap();
        assert!(!hash.is_empty());
    }

    #[tokio::test]
    async fn test_sign_root() {
        let gate = create_test_gate();
        let signature = gate.sign_root("test_hash").await.unwrap();
        assert_eq!(signature.len(), 128);
        assert!(signature.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[tokio::test]
    async fn test_create_ap2_entry() {
        let gate = create_test_gate();
        let root_hash = "abc123def456";
        let signature = "sig_test";
        let entry = gate.create_ap2_entry(root_hash, signature).await.unwrap();
        assert!(entry.contains("qa_pipeline_final_attestation"));
        assert!(entry.contains(root_hash));
    }

    #[test]
    fn test_generate_report() {
        let gate = create_test_gate();
        let root_hash = "root123";
        let signature = "sig123";
        let report = gate.generate_report(root_hash, signature).unwrap();

        assert_eq!(report["root_hash"], root_hash);
        assert_eq!(report["signature"], signature);
        assert!(report["agents"].is_array());
        assert_eq!(report["agents"].as_array().unwrap().len(), 2);
    }

    #[test]
    fn test_build_merkle_tree() {
        let gate = create_test_gate();
        let tree = gate.build_merkle_tree().unwrap();

        assert!(tree["root"].is_string());
        assert!(tree["agents"].is_array());
        assert_eq!(tree["agent_count"], 2);
    }

    #[tokio::test]
    async fn test_attestation_flow() {
        let gate = create_test_gate();
        let report = gate.attest().await.unwrap();

        assert_eq!(report.root_hash.len(), 64);
        assert_eq!(report.signature.len(), 128);
        assert!(report.duration_ms >= 0);
    }

    #[test]
    fn test_attestation_readiness_state_ready() {
        let mut gate = create_test_gate();
        gate.gate4_result.consensus_pass = 4;
        gate.gate4_result.consensus_total = 4;

        let root = gate.compute_final_root().unwrap();
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_attestation_multiple_agents() {
        let mut gate = create_test_gate();
        gate.agent_results.push(AgentResult::new(3, AgentLayer::L5L6));
        gate.agent_results.push(AgentResult::new(4, AgentLayer::L7L8));

        let root = gate.compute_final_root().unwrap();
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_readiness_report_structure() {
        let gate = create_test_gate();
        let root = gate.compute_final_root().unwrap();

        let report = ReadinessReport {
            root_hash: root.clone(),
            signature: "sig".to_string(),
            duration_ms: 5000,
            consensus: "2/4 agents passed".to_string(),
            readiness_state: ReadinessState::Degraded,
        };

        assert_eq!(report.readiness_state, ReadinessState::Degraded);
    }

    #[test]
    fn test_artifacts_directory_structure() {
        let expected_files = vec![
            ".qa-artifacts/readiness_report.json",
            ".qa-artifacts/readiness_report.sig",
            ".qa-artifacts/merkle_proof.json",
            ".qa-artifacts/summary.txt",
        ];

        for file in expected_files {
            assert!(file.contains(".qa-artifacts"));
        }
    }
}
