use core::slice;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::string::String;
use std::vec::Vec;

// ── Error Codes ─────────────────────────────────────────────────────────────
pub const ERR_SUCCESS: i32 = 0;
pub const ERR_JSON_PARSE: i32 = -1;
pub const ERR_MERKLE_BOUNDARY: i32 = -2;
pub const ERR_MERKLE_PROOF_MISMATCH: i32 = -3;
pub const ERR_SIGNATURE_INVALID: i32 = -4;
pub const ERR_TIMESTAMP_INVALID: i32 = -5;
pub const ERR_DISPOSITION_TOXIC: i32 = -6;

// ── ReceiptPayload v1.0 & v1.1 Data Models ──────────────────────────────────

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct AttestationClosure {
    pub tokenizer_digest: String,
    pub chat_template_digest: String,
    pub engine_build_digest: String,
    pub numeric_environment_digest: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ReceiptPayload {
    pub version: String,
    pub action_id: String,
    pub leaf_index: u64,
    pub tree_size: u64,
    pub timestamp: String,
    pub intent_digest: String,
    pub verdict: String,
    #[serde(default)]
    pub relying_party_verdict: Option<String>,
    pub root_hash: String,
    #[serde(default)]
    pub inclusion_proof: Vec<String>,
    #[serde(default)]
    pub attestation_closure: Option<AttestationClosure>,
    #[serde(default)]
    pub hardware_attestation: Option<serde_json::Value>,
    #[serde(default)]
    pub audit_anchor: Option<serde_json::Value>,
    pub signature: String,
    pub signer_pubkey: String,
}

// ── RFC 9162 Merkle Inclusion Verification ───────────────────────────────────

/// Computes RFC 9162 domain-separated leaf hash: SHA-256(0x00 || data)
pub fn hash_leaf(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update([0x00]);
    hasher.update(data);
    hasher.finalize().into()
}

/// Computes RFC 9162 domain-separated interior node hash: SHA-256(0x01 || left || right)
pub fn hash_children(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update([0x01]);
    hasher.update(left);
    hasher.update(right);
    hasher.finalize().into()
}

/// Verifies that leaf_hash is present at leaf_index in a Merkle tree of tree_size.
pub fn verify_inclusion(
    leaf_hash: &[u8; 32],
    leaf_index: u64,
    tree_size: u64,
    audit_path: &[[u8; 32]],
    root_hash: &[u8; 32],
) -> bool {
    if tree_size == 0 || leaf_index >= tree_size {
        return false;
    }

    if tree_size == 1 {
        return audit_path.is_empty() && leaf_hash == root_hash;
    }

    if audit_path.is_empty() {
        return false;
    }

    let mut fn_idx = leaf_index;
    let mut sn_idx = tree_size - 1;
    let mut current_hash = *leaf_hash;

    for sibling in audit_path {
        if sn_idx == 0 {
            return false;
        }
        let is_right_child = (fn_idx % 2 == 1) || (fn_idx == sn_idx);
        if is_right_child {
            current_hash = hash_children(sibling, &current_hash);
            while fn_idx.is_multiple_of(2) && (fn_idx < sn_idx) {
                fn_idx >>= 1;
                sn_idx >>= 1;
            }
        } else {
            current_hash = hash_children(&current_hash, sibling);
        }
        fn_idx >>= 1;
        sn_idx >>= 1;
    }

    current_hash == *root_hash
}

// ── Verification Engine ──────────────────────────────────────────────────────

pub fn verify_receipt_bytes(data: &[u8]) -> i32 {
    // 1. JSON Parse
    let payload: ReceiptPayload = match serde_json::from_slice(data) {
        Ok(p) => p,
        Err(_) => return ERR_JSON_PARSE,
    };

    // 2. Version Check (Supports v1.0.0 and v1.1.0)
    if payload.version != "1.0.0" && payload.version != "1.1.0" {
        return ERR_JSON_PARSE;
    }

    // 3. Merkle Ordinal Boundary Invariant: leaf_index < tree_size && tree_size >= 1
    if payload.tree_size == 0 || payload.leaf_index >= payload.tree_size {
        return ERR_MERKLE_BOUNDARY;
    }

    // 4. Validate Disposition
    let valid_dispositions = [
        "CONFIRMED",
        "UNKNOWN",
        "MISSING_EVIDENCE",
        "CONFLICT",
        "REFUSED",
        "INVALID_INPUT",
    ];
    if !valid_dispositions.contains(&payload.verdict.as_str()) {
        return ERR_JSON_PARSE;
    }

    // Validate Relying-Party Verdict if present (IETF draft-schrock-ep-action-evidence-graph-00)
    if let Some(ref rpv) = payload.relying_party_verdict {
        let valid_rp_verdicts = [
            "admissible",
            "missing_evidence",
            "stale",
            "conflicted",
            "unverifiable",
        ];
        if !valid_rp_verdicts.contains(&rpv.as_str()) {
            return ERR_JSON_PARSE;
        }
    }

    // Validate Attestation Closure if present (IETF draft-sharif-agent-audit-trail-03 §13.6)
    if let Some(ref ac) = payload.attestation_closure {
        let is_valid_digest = |s: &str| -> bool {
            s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())
        };
        if !is_valid_digest(&ac.tokenizer_digest)
            || !is_valid_digest(&ac.chat_template_digest)
            || !is_valid_digest(&ac.engine_build_digest)
            || !is_valid_digest(&ac.numeric_environment_digest)
        {
            return ERR_JSON_PARSE;
        }
    }

    // Check for toxic verdict assertions
    if payload.verdict == "TOXIC_CONFIRMED" {
        return ERR_DISPOSITION_TOXIC;
    }

    // 5. Decode Root Hash & Audit Path
    let root_bytes: [u8; 32] = match hex::decode(&payload.root_hash) {
        Ok(b) if b.len() == 32 => {
            let mut arr = [0u8; 32];
            arr.copy_from_slice(&b);
            arr
        }
        _ => return ERR_JSON_PARSE,
    };

    let mut audit_path = Vec::new();
    for p in &payload.inclusion_proof {
        match hex::decode(p) {
            Ok(b) if b.len() == 32 => {
                let mut arr = [0u8; 32];
                arr.copy_from_slice(&b);
                audit_path.push(arr);
            }
            _ => return ERR_JSON_PARSE,
        }
    }

    // 6. Compute Leaf Hash from intent_digest & action_id
    let intent_bytes = match hex::decode(&payload.intent_digest) {
        Ok(b) if b.len() == 32 => b,
        _ => return ERR_JSON_PARSE,
    };

    let mut leaf_content = Vec::new();
    leaf_content.extend_from_slice(payload.action_id.as_bytes());
    leaf_content.extend_from_slice(&intent_bytes);
    leaf_content.extend_from_slice(payload.verdict.as_bytes());
    let computed_leaf_hash = hash_leaf(&leaf_content);

    // 7. Verify Merkle Inclusion Proof
    if !verify_inclusion(
        &computed_leaf_hash,
        payload.leaf_index,
        payload.tree_size,
        &audit_path,
        &root_bytes,
    ) {
        return ERR_MERKLE_PROOF_MISMATCH;
    }

    // 8. Verify Ed25519 Signature
    let pubkey_bytes: [u8; 32] = match hex::decode(&payload.signer_pubkey) {
        Ok(b) if b.len() == 32 => {
            let mut arr = [0u8; 32];
            arr.copy_from_slice(&b);
            arr
        }
        _ => return ERR_JSON_PARSE,
    };

    let sig_bytes: [u8; 64] = match hex::decode(&payload.signature) {
        Ok(b) if b.len() == 64 => {
            let mut arr = [0u8; 64];
            arr.copy_from_slice(&b);
            arr
        }
        _ => return ERR_JSON_PARSE,
    };

    let verifying_key = match VerifyingKey::from_bytes(&pubkey_bytes) {
        Ok(k) => k,
        Err(_) => return ERR_SIGNATURE_INVALID,
    };

    let signature = Signature::from_bytes(&sig_bytes);

    // Signed message: root_hash + action_id + verdict + timestamp
    let mut signed_msg = Vec::new();
    signed_msg.extend_from_slice(&root_bytes);
    signed_msg.extend_from_slice(payload.action_id.as_bytes());
    signed_msg.extend_from_slice(payload.verdict.as_bytes());
    signed_msg.extend_from_slice(payload.timestamp.as_bytes());

    if verifying_key.verify(&signed_msg, &signature).is_err() {
        return ERR_SIGNATURE_INVALID;
    }

    // 9. Basic Timestamp Year Sanity (Reject ancient/future skew)
    if payload.timestamp.len() >= 4 {
        if let Ok(year) = payload.timestamp[0..4].parse::<i32>() {
            if !(2024..=2030).contains(&year) {
                return ERR_TIMESTAMP_INVALID;
            }
        }
    }

    ERR_SUCCESS
}

// ── WASM C-ABI Exports ───────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn allocate(size: usize) -> *mut u8 {
    let mut buffer = Vec::with_capacity(size);
    let ptr = buffer.as_mut_ptr();
    core::mem::forget(buffer);
    ptr
}

/// # Safety
///
/// Deallocates memory previously allocated by `allocate`.
/// The caller must ensure `ptr` points to a valid allocation of `size` bytes.
#[no_mangle]
pub unsafe extern "C" fn deallocate(ptr: *mut u8, size: usize) {
    let _ = Vec::from_raw_parts(ptr, 0, size);
}

/// # Safety
///
/// Verifies a receipt payload in memory.
/// The caller must ensure `ptr` points to a valid readable byte buffer of length `len`.
#[no_mangle]
pub unsafe extern "C" fn smaos_verify_receipt(ptr: *const u8, len: usize) -> i32 {
    if ptr.is_null() || len == 0 {
        return ERR_JSON_PARSE;
    }
    let slice = slice::from_raw_parts(ptr, len);
    verify_receipt_bytes(slice)
}

#[no_mangle]
pub extern "C" fn smaos_version() -> i32 {
    110 // 1.1.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;

    #[test]
    fn test_version() {
        assert_eq!(smaos_version(), 110);
    }

    #[test]
    fn test_merkle_single_leaf() {
        let leaf = hash_leaf(b"leaf_0");
        assert!(verify_inclusion(&leaf, 0, 1, &[], &leaf));
        assert!(!verify_inclusion(&leaf, 1, 1, &[], &leaf));
        assert!(!verify_inclusion(&leaf, 0, 0, &[], &leaf));
    }

    #[test]
    fn test_boundary_rejection() {
        assert_eq!(
            verify_receipt_bytes(br#"{
                "version": "1.0.0",
                "action_id": "act-1",
                "leaf_index": 5,
                "tree_size": 5,
                "timestamp": "2026-09-18T12:00:00Z",
                "intent_digest": "0000000000000000000000000000000000000000000000000000000000000000",
                "verdict": "CONFIRMED",
                "root_hash": "0000000000000000000000000000000000000000000000000000000000000000",
                "signature": "00",
                "signer_pubkey": "00"
            }"#),
            ERR_MERKLE_BOUNDARY
        );
    }

    #[test]
    fn test_valid_signed_receipt() {
        let csprng = [42u8; 32];
        let signing_key = SigningKey::from_bytes(&csprng);
        let verifying_key = signing_key.verifying_key();
        let pubkey_hex = hex::encode(verifying_key.as_bytes());

        let action_id = "act-valid-001";
        let intent_hex = "1111111111111111111111111111111111111111111111111111111111111111";
        let intent_bytes = hex::decode(intent_hex).unwrap();
        let verdict = "CONFIRMED";
        let timestamp = "2026-09-18T12:00:00Z";

        let mut leaf_content = Vec::new();
        leaf_content.extend_from_slice(action_id.as_bytes());
        leaf_content.extend_from_slice(&intent_bytes);
        leaf_content.extend_from_slice(verdict.as_bytes());
        let root = hash_leaf(&leaf_content);
        let root_hex = hex::encode(root);

        let mut signed_msg = Vec::new();
        signed_msg.extend_from_slice(&root);
        signed_msg.extend_from_slice(action_id.as_bytes());
        signed_msg.extend_from_slice(verdict.as_bytes());
        signed_msg.extend_from_slice(timestamp.as_bytes());

        use ed25519_dalek::Signer;
        let sig = signing_key.sign(&signed_msg);
        let sig_hex = hex::encode(sig.to_bytes());

        let payload_json = format!(r#"{{
            "version": "1.0.0",
            "action_id": "{}",
            "leaf_index": 0,
            "tree_size": 1,
            "timestamp": "{}",
            "intent_digest": "{}",
            "verdict": "{}",
            "root_hash": "{}",
            "inclusion_proof": [],
            "signature": "{}",
            "signer_pubkey": "{}"
        }}"#, action_id, timestamp, intent_hex, verdict, root_hex, sig_hex, pubkey_hex);

        assert_eq!(verify_receipt_bytes(payload_json.as_bytes()), ERR_SUCCESS);

        // Tampered signature should fail
        let mut tampered_sig = sig.to_bytes();
        tampered_sig[0] ^= 0xFF;
        let tampered_sig_hex = hex::encode(tampered_sig);
        let tampered_json = payload_json.replace(&sig_hex, &tampered_sig_hex);
        assert_eq!(verify_receipt_bytes(tampered_json.as_bytes()), ERR_SIGNATURE_INVALID);
    }

    #[test]
    fn test_valid_v1_1_with_attestation_closure_and_relying_party_verdict() {
        let csprng = [99u8; 32];
        let signing_key = SigningKey::from_bytes(&csprng);
        let verifying_key = signing_key.verifying_key();
        let pubkey_hex = hex::encode(verifying_key.as_bytes());

        let action_id = "act-v11-001";
        let intent_hex = "2222222222222222222222222222222222222222222222222222222222222222";
        let intent_bytes = hex::decode(intent_hex).unwrap();
        let verdict = "CONFIRMED";
        let timestamp = "2026-09-18T14:30:00Z";

        let mut leaf_content = Vec::new();
        leaf_content.extend_from_slice(action_id.as_bytes());
        leaf_content.extend_from_slice(&intent_bytes);
        leaf_content.extend_from_slice(verdict.as_bytes());
        let root = hash_leaf(&leaf_content);
        let root_hex = hex::encode(root);

        let mut signed_msg = Vec::new();
        signed_msg.extend_from_slice(&root);
        signed_msg.extend_from_slice(action_id.as_bytes());
        signed_msg.extend_from_slice(verdict.as_bytes());
        signed_msg.extend_from_slice(timestamp.as_bytes());

        use ed25519_dalek::Signer;
        let sig = signing_key.sign(&signed_msg);
        let sig_hex = hex::encode(sig.to_bytes());

        let d64 = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789";

        let payload_json = format!(r#"{{
            "version": "1.1.0",
            "action_id": "{}",
            "leaf_index": 0,
            "tree_size": 1,
            "timestamp": "{}",
            "intent_digest": "{}",
            "verdict": "{}",
            "relying_party_verdict": "admissible",
            "root_hash": "{}",
            "inclusion_proof": [],
            "attestation_closure": {{
                "tokenizer_digest": "{}",
                "chat_template_digest": "{}",
                "engine_build_digest": "{}",
                "numeric_environment_digest": "{}"
            }},
            "hardware_attestation": {{
                "tpm_quote": "mock-tpm-quote-data"
            }},
            "signature": "{}",
            "signer_pubkey": "{}"
        }}"#, action_id, timestamp, intent_hex, verdict, root_hex, d64, d64, d64, d64, sig_hex, pubkey_hex);

        assert_eq!(verify_receipt_bytes(payload_json.as_bytes()), ERR_SUCCESS);

        // Invalid relying_party_verdict
        let invalid_rpv = payload_json.replace("\"admissible\"", "\"illegal_verdict\"");
        assert_eq!(verify_receipt_bytes(invalid_rpv.as_bytes()), ERR_JSON_PARSE);

        // Invalid attestation closure digest (e.g. truncated)
        let truncated_digest = payload_json.replace(d64, "tooshort");
        assert_eq!(verify_receipt_bytes(truncated_digest.as_bytes()), ERR_JSON_PARSE);
    }
}
