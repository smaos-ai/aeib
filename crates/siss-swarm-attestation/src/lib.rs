use ed25519_dalek::{Signer, SigningKey, Verifier};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Instant;
use uuid::Uuid;

// Phase 74.5: HPC-Yield scheduling + Formal verification
pub mod policy;
pub mod scheduler;

/// Node identifier in the swarm
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NodeId(Uuid);

impl NodeId {
    pub fn new() -> Self {
        NodeId(Uuid::new_v4())
    }
}

/// Ed25519 attestation signature for cross-node trust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeAttestation {
    pub node_id: NodeId,
    pub state_hash: String,
    pub signature: Vec<u8>,
    pub timestamp: u64,
}

/// Merkle DAG node in the append-only swarm state ledger
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateEntry {
    pub entry_id: Uuid,
    pub node_id: NodeId,
    pub state_hash: String,
    pub parent_hash: Option<String>,
    pub attestation: Option<NodeAttestation>,
    pub timestamp: u64,
}

/// Swarm state ledger - append-only, immutable
pub struct SwarmState {
    entries: Vec<StateEntry>,
    node_keys: HashMap<NodeId, SigningKey>,
    peer_public_keys: HashMap<NodeId, ed25519_dalek::VerifyingKey>,
    last_hash: String,
}

impl SwarmState {
    pub fn new() -> Self {
        SwarmState {
            entries: Vec::new(),
            node_keys: HashMap::new(),
            peer_public_keys: HashMap::new(),
            last_hash: String::from("genesis"),
        }
    }

    /// Register a node with its Ed25519 signing key
    pub fn register_node(&mut self, node_id: NodeId, signing_key: SigningKey) {
        // PHASE 63: Store public key for peer verification
        let public_key = signing_key.verifying_key();
        self.peer_public_keys.insert(node_id, public_key);
        self.node_keys.insert(node_id, signing_key);
    }

    /// Append a new state entry to the ledger (fail-closed on overwrites)
    pub fn append_state(&mut self, entry: StateEntry) -> Result<(), String> {
        // PHASE 63 CONSTRAINT: Append-only, no overwrites
        // Check if this entry_id already exists
        if self.entries.iter().any(|e| e.entry_id == entry.entry_id) {
            return Err(
                "STATE_OVERWRITE_ATTEMPT: Cannot overwrite existing state entry".to_string(),
            );
        }

        // Verify parent hash chain
        if let Some(parent) = &entry.parent_hash {
            if parent != &self.last_hash {
                return Err(
                    "MERKLE_DAG_VIOLATION: Parent hash does not match chain head".to_string(),
                );
            }
        }

        self.entries.push(entry.clone());
        self.last_hash = entry.state_hash.clone();
        Ok(())
    }

    /// Sign a state update with the node's private key
    pub fn sign_state(&self, node_id: NodeId, state_hash: &str) -> Result<Vec<u8>, String> {
        let key = self.node_keys.get(&node_id).ok_or("Node not registered")?;

        let message = state_hash.as_bytes();
        let signature = key.sign(message);
        Ok(signature.to_bytes().to_vec())
    }

    /// Verify a peer's attestation signature
    pub fn verify_peer_attestation(&self, attestation: &NodeAttestation) -> Result<(), String> {
        // PHASE 63: Lookup peer's public key and verify signature
        let public_key = self
            .peer_public_keys
            .get(&attestation.node_id)
            .ok_or("Peer public key not found in registry")?;

        let signature = ed25519_dalek::Signature::from_bytes(
            &attestation
                .signature
                .as_slice()
                .try_into()
                .map_err(|_| "Invalid signature format")?,
        );

        public_key
            .verify(attestation.state_hash.as_bytes(), &signature)
            .map_err(|_| "Signature verification failed".to_string())
    }

    /// Get the current attestation for this node
    pub fn get_node_attestation(&self, node_id: NodeId) -> Result<NodeAttestation, String> {
        let state_hash = self.last_hash.clone();
        let signature = self.sign_state(node_id, &state_hash)?;

        Ok(NodeAttestation {
            node_id,
            state_hash,
            signature,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        })
    }

    pub fn entries(&self) -> &[StateEntry] {
        &self.entries
    }

    pub fn last_hash(&self) -> &str {
        &self.last_hash
    }
}

pub mod mcp {
    use super::*;
    use sha2::{Digest, Sha256};

    // ====== Phase 74: SwarmState with Merkle root + attestation ======
    #[derive(Clone, Serialize, Deserialize, Debug)]
    pub struct MerkleSwarmState {
        pub idempotency_key: String,
        pub status: String,
        pub phase: String,
        pub payload_json: Option<String>,
        pub created_at: chrono::DateTime<chrono::Utc>,
        pub updated_at: chrono::DateTime<chrono::Utc>,
        pub merkle_root: Option<String>,
        pub attestation_sig: Option<String>,
        pub node_id: String,
    }

    // Phase 74: Merkle root computation
    pub fn compute_merkle_root(states: &[MerkleSwarmState]) -> String {
        let mut hashes: Vec<[u8; 32]> = states
            .iter()
            .map(|s| {
                let mut hasher = Sha256::new();
                hasher.update(format!(
                    "{}:{}:{}:{}",
                    s.idempotency_key,
                    s.status,
                    s.phase,
                    s.payload_json.as_deref().unwrap_or("")
                ));
                hasher.finalize().into()
            })
            .collect();

        while hashes.len() > 1 {
            let mut next_level = Vec::new();
            for chunk in hashes.chunks(2) {
                let mut hasher = Sha256::new();
                hasher.update(chunk[0]);
                if chunk.len() > 1 {
                    hasher.update(chunk[1]);
                }
                next_level.push(hasher.finalize().into());
            }
            hashes = next_level;
        }
        hex::encode(hashes.first().unwrap_or(&[0u8; 32]))
    }

    // Phase 74: Sign state with Ed25519
    pub fn sign_state(state: &MerkleSwarmState, key: &SigningKey) -> Result<String, String> {
        let msg = format!(
            "{}:{}:{}",
            state.node_id,
            state.merkle_root.as_ref().unwrap_or(&"".to_string()),
            state.updated_at.timestamp()
        );
        let sig = key.sign(msg.as_bytes());
        Ok(hex::encode(sig.to_bytes()))
    }

    // Phase 74: Verify peer attestation
    pub fn verify_peer_attestation(
        node_id: &str,
        merkle_root: &str,
        sig_hex: &str,
        peer_key: &ed25519_dalek::VerifyingKey,
    ) -> Result<bool, String> {
        use ed25519_dalek::Verifier;
        let msg = format!(
            "{}:{}:{}",
            node_id,
            merkle_root,
            chrono::Utc::now().timestamp()
        );
        let sig_bytes = hex::decode(sig_hex).map_err(|e| e.to_string())?;
        let sig = ed25519_dalek::Signature::from_slice(&sig_bytes)
            .map_err(|_| "Invalid Ed25519 signature format".to_string())?;

        Ok(peer_key.verify(msg.as_bytes(), &sig).is_ok())
    }

    /// MCP contract for get_node_attestation
    #[derive(Debug, Serialize, Deserialize)]
    pub struct GetNodeAttestationInput {
        pub node_id: String,
    }

    #[derive(Debug, Serialize, Deserialize)]
    pub struct GetNodeAttestationOutput {
        pub node_id: String,
        pub state_hash: String,
        pub signature: String,
        pub timestamp: u64,
    }

    /// MCP contract for verify_peer_attestation
    #[derive(Debug, Serialize, Deserialize)]
    pub struct VerifyPeerAttestationInput {
        pub node_id: String,
        pub state_hash: String,
        pub signature: String,
        pub timestamp: u64,
    }

    #[derive(Debug, Serialize, Deserialize)]
    pub struct VerifyPeerAttestationOutput {
        pub valid: bool,
        pub reason: Option<String>,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;
    use rand::Rng;

    fn create_signing_key() -> SigningKey {
        let mut csprng = rand::thread_rng();
        let mut bytes = [0u8; 32];
        csprng.fill(&mut bytes);
        SigningKey::from_bytes(&bytes)
    }

    // ============================================================================
    // PHASE 63: CROSS-NODE ATTESTATION (RED PHASE - FAILING TESTS)
    // ============================================================================

    #[test]
    fn test_ed25519_attestation_signing_latency_trap() {
        // CONSTRAINT: Ed25519 signing and verification must execute within <1ms latency budget
        // This is critical for maintaining swarm consensus at scale

        let node_id = NodeId::new();
        let mut state = SwarmState::new();
        let signing_key = create_signing_key();
        state.register_node(node_id, signing_key);

        let state_hash = "test_state_hash_v1";

        // Measure signing latency
        let sign_start = Instant::now();
        let _signature = state
            .sign_state(node_id, state_hash)
            .expect("Signing must succeed");
        let sign_latency_ms = sign_start.elapsed().as_secs_f64() * 1000.0;

        assert!(
            sign_latency_ms < 0.5,
            "ED25519 LATENCY VIOLATION: Signing took {}ms, must be < 0.5ms (strict budget)",
            sign_latency_ms
        );

        // Measure attestation generation latency
        let attest_start = Instant::now();
        let _attestation = state
            .get_node_attestation(node_id)
            .expect("Attestation generation must succeed");
        let attest_latency_ms = attest_start.elapsed().as_secs_f64() * 1000.0;

        assert!(
            attest_latency_ms < 0.5,
            "ED25519 ATTESTATION LATENCY VIOLATION: Generation took {}ms, must be < 0.5ms",
            attest_latency_ms
        );

        // Both operations combined must still be < 0.8ms (strict budget enforcement)
        let total_latency = sign_latency_ms + attest_latency_ms;
        assert!(
            total_latency < 0.8,
            "ED25519 TOTAL LATENCY VIOLATION: {}ms + {}ms = {}ms, must be < 0.8ms (RED PHASE CONSTRAINT)",
            sign_latency_ms,
            attest_latency_ms,
            total_latency
        );
    }

    #[test]
    fn test_merkle_dag_append_only_immutability() {
        // CONSTRAINT: Swarm state ledger is append-only and immutable
        // Any attempt to overwrite an existing state entry must trigger a fail-closed panic

        let node_id = NodeId::new();
        let mut state = SwarmState::new();
        let signing_key = create_signing_key();
        state.register_node(node_id, signing_key);

        let entry_id = Uuid::new_v4();
        let state_hash = "hash_v1";

        // Create initial state entry
        let entry1 = StateEntry {
            entry_id,
            node_id,
            state_hash: state_hash.to_string(),
            parent_hash: Some("genesis".to_string()),
            attestation: None,
            timestamp: 1000,
        };

        // ASSERTION 1: Appending a new entry succeeds
        let result = state.append_state(entry1.clone());
        assert!(
            result.is_ok(),
            "MERKLE DAG VIOLATION: Initial state append must succeed"
        );

        // ASSERTION 2: Attempting to append the same entry_id again must fail
        let entry2 = StateEntry {
            entry_id, // Same ID - this is an overwrite attempt
            node_id,
            state_hash: "hash_v2_modified".to_string(),
            parent_hash: Some(state_hash.to_string()),
            attestation: None,
            timestamp: 2000,
        };

        let overwrite_result = state.append_state(entry2);
        assert!(
            overwrite_result.is_err(),
            "MERKLE DAG VIOLATION: Overwrite attempt must be rejected"
        );

        match overwrite_result {
            Err(msg) => {
                assert!(
                    msg.contains("OVERWRITE"),
                    "MERKLE DAG VIOLATION: Error must mention STATE_OVERWRITE_ATTEMPT, got: {}",
                    msg
                );
            }
            Ok(_) => {
                panic!("MERKLE DAG VIOLATION: Overwrite must fail-close (return Err)");
            }
        }

        // ASSERTION 3: Verify ledger integrity - chain is unbroken
        let entries = state.entries();
        assert_eq!(
            entries.len(),
            1,
            "MERKLE DAG VIOLATION: Ledger must contain exactly 1 entry"
        );
        assert_eq!(
            entries[0].state_hash, state_hash,
            "MERKLE DAG VIOLATION: Entry state_hash must match"
        );
    }

    #[test]
    fn test_merkle_dag_parent_hash_chain() {
        // CONSTRAINT: Merkle DAG chain integrity - each entry's parent_hash must match the previous entry's state_hash

        let node_id = NodeId::new();
        let mut state = SwarmState::new();
        let signing_key = create_signing_key();
        state.register_node(node_id, signing_key);

        // Entry 1: genesis parent
        let entry1 = StateEntry {
            entry_id: Uuid::new_v4(),
            node_id,
            state_hash: "hash_v1".to_string(),
            parent_hash: Some("genesis".to_string()),
            attestation: None,
            timestamp: 1000,
        };

        state
            .append_state(entry1)
            .expect("First append must succeed");

        // Entry 2: correct parent hash
        let entry2 = StateEntry {
            entry_id: Uuid::new_v4(),
            node_id,
            state_hash: "hash_v2".to_string(),
            parent_hash: Some("hash_v1".to_string()), // Correct parent
            attestation: None,
            timestamp: 2000,
        };

        let result2 = state.append_state(entry2);
        assert!(
            result2.is_ok(),
            "MERKLE DAG VIOLATION: Entry with correct parent_hash must be appended"
        );

        // Entry 3: WRONG parent hash (breaks chain)
        let entry3 = StateEntry {
            entry_id: Uuid::new_v4(),
            node_id,
            state_hash: "hash_v3".to_string(),
            parent_hash: Some("wrong_hash".to_string()), // Wrong parent!
            attestation: None,
            timestamp: 3000,
        };

        let result3 = state.append_state(entry3);
        assert!(
            result3.is_err(),
            "MERKLE DAG VIOLATION: Entry with wrong parent_hash must be rejected"
        );

        match result3 {
            Err(msg) => {
                assert!(
                    msg.contains("MERKLE_DAG_VIOLATION"),
                    "MERKLE DAG VIOLATION: Error must mention DAG violation, got: {}",
                    msg
                );
            }
            Ok(_) => {
                panic!("MERKLE DAG VIOLATION: Chain integrity check must fail");
            }
        }
    }

    #[test]
    fn test_mcp_contracts_get_node_attestation_schema() {
        // CONSTRAINT: get_node_attestation() MCP tool must return strictly compliant JSON schema
        // Required fields: node_id, state_hash, signature, timestamp (RFC3339 or Unix epoch)

        let node_id = NodeId::new();
        let mut state = SwarmState::new();
        let signing_key = create_signing_key();
        state.register_node(node_id, signing_key);

        let attestation = state
            .get_node_attestation(node_id)
            .expect("get_node_attestation must succeed");

        // ASSERTION 1: Attestation struct must have all required fields
        assert!(
            !attestation.state_hash.is_empty(),
            "MCP CONTRACT VIOLATION: state_hash must not be empty"
        );
        assert!(
            !attestation.signature.is_empty(),
            "MCP CONTRACT VIOLATION: signature must not be empty"
        );
        assert!(
            attestation.timestamp > 0,
            "MCP CONTRACT VIOLATION: timestamp must be > 0"
        );
        assert_eq!(
            attestation.node_id, node_id,
            "MCP CONTRACT VIOLATION: node_id must match request"
        );

        // ASSERTION 2: Verify JSON serialization to MCP output schema
        let output = mcp::GetNodeAttestationOutput {
            node_id: attestation.node_id.0.to_string(),
            state_hash: attestation.state_hash.clone(),
            signature: hex::encode(&attestation.signature),
            timestamp: attestation.timestamp,
        };

        let json = serde_json::to_string(&output).expect("Serialization must succeed");
        assert!(
            json.contains("\"node_id\""),
            "MCP CONTRACT VIOLATION: Output must have node_id field"
        );
        assert!(
            json.contains("\"state_hash\""),
            "MCP CONTRACT VIOLATION: Output must have state_hash field"
        );
        assert!(
            json.contains("\"signature\""),
            "MCP CONTRACT VIOLATION: Output must have signature field"
        );
        assert!(
            json.contains("\"timestamp\""),
            "MCP CONTRACT VIOLATION: Output must have timestamp field"
        );

        // ASSERTION 3: Verify deserialization round-trip
        let _deserialized: mcp::GetNodeAttestationOutput =
            serde_json::from_str(&json).expect("MCP schema must be deserializable");
    }

    #[test]
    fn test_mcp_contracts_verify_peer_attestation_schema() {
        // CONSTRAINT: verify_peer_attestation() MCP tool must accept strict schema
        // Required input: node_id, state_hash, signature, timestamp
        // Required output: valid (bool), reason (Option<String>)

        let node_id = NodeId::new();
        let mut state = SwarmState::new();
        let signing_key = create_signing_key();
        state.register_node(node_id, signing_key);

        let attestation = state
            .get_node_attestation(node_id)
            .expect("get_node_attestation must succeed");

        // ASSERTION 1: Construct proper MCP input schema
        let verify_input = mcp::VerifyPeerAttestationInput {
            node_id: attestation.node_id.0.to_string(),
            state_hash: attestation.state_hash.clone(),
            signature: hex::encode(&attestation.signature),
            timestamp: attestation.timestamp,
        };

        // ASSERTION 2: Verify input schema serialization
        let input_json = serde_json::to_string(&verify_input).expect("Input schema must serialize");
        assert!(
            input_json.contains("\"node_id\""),
            "MCP INPUT VIOLATION: node_id required"
        );
        assert!(
            input_json.contains("\"state_hash\""),
            "MCP INPUT VIOLATION: state_hash required"
        );
        assert!(
            input_json.contains("\"signature\""),
            "MCP INPUT VIOLATION: signature required"
        );
        assert!(
            input_json.contains("\"timestamp\""),
            "MCP INPUT VIOLATION: timestamp required"
        );

        // ASSERTION 3: Verify output schema structure
        let verify_output = mcp::VerifyPeerAttestationOutput {
            valid: false,
            reason: Some("Stub implementation not yet ready".to_string()),
        };

        let output_json =
            serde_json::to_string(&verify_output).expect("Output schema must serialize");
        assert!(
            output_json.contains("\"valid\""),
            "MCP OUTPUT VIOLATION: valid field required"
        );
        assert!(
            output_json.contains("\"reason\""),
            "MCP OUTPUT VIOLATION: reason field required"
        );

        // ASSERTION 4: Verify attestation with the implementation
        let verify_result = state.verify_peer_attestation(&attestation);
        assert!(
            verify_result.is_ok(),
            "PHASE 63 GREEN: verify_peer_attestation must successfully verify valid attestations"
        );
    }

    #[test]
    fn test_peer_attestation_verification_must_be_implemented() {
        // CONSTRAINT: verify_peer_attestation MUST be implemented (not stubbed)
        // This test FAILS in RED phase because verification is just a stub
        // It will PASS in GREEN phase when actual verification logic is added

        let node_id = NodeId::new();
        let mut state = SwarmState::new();
        let signing_key = create_signing_key();
        state.register_node(node_id, signing_key);

        let attestation = state
            .get_node_attestation(node_id)
            .expect("get_node_attestation must work");

        // ASSERTION: verify_peer_attestation must succeed for valid attestations
        let verify_result = state.verify_peer_attestation(&attestation);
        assert!(
            verify_result.is_ok(),
            "PHASE 63 RED CONSTRAINT: verify_peer_attestation must be fully implemented, not stubbed. Got Err: {:?}",
            verify_result
        );
    }

    #[test]
    fn test_mcp_contracts_schema_compliance() {
        // CONSTRAINT: Both MCP contracts must strictly adhere to Model Context Protocol
        // Input/output must be JSON-serializable with proper type declarations

        // Test GetNodeAttestationInput schema
        let get_input = mcp::GetNodeAttestationInput {
            node_id: "550e8400-e29b-41d4-a716-446655440000".to_string(),
        };
        let get_input_json = serde_json::to_string(&get_input).expect("Must serialize");
        let _get_input_parsed: mcp::GetNodeAttestationInput = serde_json::from_str(&get_input_json)
            .expect("MCP SCHEMA VIOLATION: GetNodeAttestationInput must round-trip");

        // Test GetNodeAttestationOutput schema
        let get_output = mcp::GetNodeAttestationOutput {
            node_id: "550e8400-e29b-41d4-a716-446655440000".to_string(),
            state_hash: "abc123def456".to_string(),
            signature: "deadbeefcafe".to_string(),
            timestamp: 1234567890,
        };
        let get_output_json = serde_json::to_string(&get_output).expect("Must serialize");
        let _get_output_parsed: mcp::GetNodeAttestationOutput =
            serde_json::from_str(&get_output_json)
                .expect("MCP SCHEMA VIOLATION: GetNodeAttestationOutput must round-trip");

        // Test VerifyPeerAttestationInput schema
        let verify_input = mcp::VerifyPeerAttestationInput {
            node_id: "550e8400-e29b-41d4-a716-446655440000".to_string(),
            state_hash: "abc123def456".to_string(),
            signature: "deadbeefcafe".to_string(),
            timestamp: 1234567890,
        };
        let verify_input_json = serde_json::to_string(&verify_input).expect("Must serialize");
        let _verify_input_parsed: mcp::VerifyPeerAttestationInput =
            serde_json::from_str(&verify_input_json)
                .expect("MCP SCHEMA VIOLATION: VerifyPeerAttestationInput must round-trip");

        // Test VerifyPeerAttestationOutput schema
        let verify_output = mcp::VerifyPeerAttestationOutput {
            valid: true,
            reason: None,
        };
        let verify_output_json = serde_json::to_string(&verify_output).expect("Must serialize");
        let _verify_output_parsed: mcp::VerifyPeerAttestationOutput =
            serde_json::from_str(&verify_output_json)
                .expect("MCP SCHEMA VIOLATION: VerifyPeerAttestationOutput must round-trip");

        // All schemas must pass - if any fail, the test fails
        assert!(true, "All MCP schemas are compliant");
    }
}
