use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::sync::{Arc, Mutex};
use std::time::Instant;

#[derive(Debug, Clone, PartialEq)]
pub enum CapsuleError {
    UnauthorizedTool,
    EmptyLog,
    LockPoisoned,
}

pub type CapsuleResult<T> = Result<T, CapsuleError>;

#[derive(Debug, Clone, PartialEq)]
pub struct MerkleProof {
    pub hash: [u8; 32],
    pub confidence: f64,
    pub execution_nanos: u64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ToolCall {
    pub tool_name: String,
    pub params_hash: [u8; 32],
    pub timestamp: i64,
    pub approved: bool,
}

#[derive(Debug, Default)]
struct ToolState {
    approved_tools: HashSet<String>,
    call_log: Vec<ToolCall>,
}

pub struct ToolCallCapsule {
    state: Arc<Mutex<ToolState>>,
}

impl ToolCallCapsule {
    pub fn new() -> Self {
        Self {
            state: Arc::new(Mutex::new(ToolState::default())),
        }
    }

    pub fn authorize_tool(&self, tool_name: &str) -> CapsuleResult<()> {
        let mut state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;
        state.approved_tools.insert(tool_name.to_string());
        Ok(())
    }

    pub fn verify_authorization(
        &self,
        tool_name: &str,
        params: &[u8],
    ) -> CapsuleResult<MerkleProof> {
        let start = Instant::now();

        let mut state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;

        // Fail-closed gate: unauthorized tools rejected
        if !state.approved_tools.contains(tool_name) {
            return Err(CapsuleError::UnauthorizedTool);
        }

        // Hash: tool_name || "|" || params_hash
        let mut params_hasher = Sha256::new();
        params_hasher.update(params);
        let params_digest = params_hasher.finalize();
        let mut params_hash = [0u8; 32];
        params_hash.copy_from_slice(&params_digest);

        let mut hasher = Sha256::new();
        hasher.update(tool_name.as_bytes());
        hasher.update(b"|");
        hasher.update(params_hash);
        let digest = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&digest);

        let execution_nanos = start.elapsed().as_nanos() as u64;

        let tool_call = ToolCall {
            tool_name: tool_name.to_string(),
            params_hash,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs() as i64,
            approved: true,
        };
        state.call_log.push(tool_call);

        let confidence = self.compute_confidence(&state);

        Ok(MerkleProof {
            hash,
            confidence,
            execution_nanos,
        })
    }

    fn compute_confidence(&self, state: &ToolState) -> f64 {
        if state.call_log.is_empty() {
            return 0.0;
        }
        let approved = state
            .call_log
            .iter()
            .filter(|c| c.approved)
            .count() as f64;
        let total = state.call_log.len() as f64;
        approved / total
    }

    pub fn get_confidence(&self) -> f64 {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        self.compute_confidence(&state)
    }
}

impl Default for ToolCallCapsule {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tool_authorization_basic() {
        let capsule = ToolCallCapsule::new();
        capsule.authorize_tool("read_file").unwrap();
        let result = capsule.verify_authorization("read_file", b"params");
        assert!(result.is_ok());
        let proof = result.unwrap();
        assert_eq!(proof.hash.len(), 32);
        assert!(proof.confidence >= 0.0 && proof.confidence <= 1.0);
    }

    #[test]
    fn test_unauthorized_tool_rejected() {
        let capsule = ToolCallCapsule::new();
        capsule.authorize_tool("read_file").unwrap();
        let result = capsule.verify_authorization("delete_all", b"params");
        assert!(matches!(result.unwrap_err(), CapsuleError::UnauthorizedTool));
    }

    #[test]
    fn test_merkle_proof_generation() {
        let capsule = ToolCallCapsule::new();
        capsule.authorize_tool("compute").unwrap();
        let proof = capsule.verify_authorization("compute", b"test_params").unwrap();
        assert_ne!(proof.hash, [0u8; 32]);
    }

    #[test]
    fn test_concurrent_calls() {
        let capsule = Arc::new(ToolCallCapsule::new());
        capsule.authorize_tool("log").unwrap();

        let handles: Vec<_> = (0..4)
            .map(|i| {
                let cap = Arc::clone(&capsule);
                std::thread::spawn(move || {
                    let params = format!("param_{}", i).into_bytes();
                    cap.verify_authorization("log", &params)
                })
            })
            .collect();

        for handle in handles {
            let result = handle.join().expect("thread panicked");
            assert!(result.is_ok());
        }
    }

    #[test]
    fn test_proof_deterministic() {
        let capsule = ToolCallCapsule::new();
        capsule.authorize_tool("hash_check").unwrap();
        let proof_a = capsule.verify_authorization("hash_check", b"data").unwrap();

        let capsule2 = ToolCallCapsule::new();
        capsule2.authorize_tool("hash_check").unwrap();
        let proof_b = capsule2.verify_authorization("hash_check", b"data").unwrap();

        assert_eq!(proof_a.hash, proof_b.hash);
    }
}
