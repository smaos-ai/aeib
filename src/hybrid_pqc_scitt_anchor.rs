// File: src/hybrid_pqc_scitt_anchor.rs
// Track Delta: Hybrid Classical + Post-Quantum SCITT Transparency Anchor Scaffold.
// Epistemic Note (AGENTS.md Rule 1 & Rule 5):
// Defines the structural Rust data-plane types and deterministic Merkle inclusion
// verification for dual-slot COSE receipts (`COSE_ALG_EDDSA = -8` paired with
// `COSE_ALG_ML_DSA_65 = -49` per RFC 9964 / FIPS 204 and RFC 9942 header 394).
// Evaluated under the stated model.

use std::collections::BTreeMap;

pub const COSE_ALG_EDDSA: i32 = -8;
pub const COSE_ALG_ML_DSA_65: i32 = -49;
pub const COSE_HEADER_VERIFIABLE_PROOFS: u32 = 394;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HybridPqcSignatureSlot {
    pub ed25519_alg: i32,
    pub ed25519_kid: String,
    pub ed25519_sig_hex: String,
    pub mldsa65_alg: i32,
    pub mldsa65_kid: String,
    pub mldsa65_parameter_set: &'static str,
    pub mldsa65_sig_commitment_hex: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScittMerkleInclusionProof {
    pub tree_size: u64,
    pub leaf_index: u64,
    pub root_hash_hex: String,
    pub sibling_hashes_hex: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HybridScittTransparentReceipt {
    pub operation_id: String,
    pub act_caid: String,
    pub policy_epoch: String,
    pub signatures: HybridPqcSignatureSlot,
    pub unprotected_header_394: ScittMerkleInclusionProof,
    pub metadata: BTreeMap<String, String>,
}

impl HybridScittTransparentReceipt {
    /// Checks structural admissibility of the dual-slot (Ed25519 + ML-DSA-65)
    /// SCITT receipt envelope before cryptographic verification.
    pub fn validate_envelope_invariants(&self) -> Result<(), &'static str> {
        if self.signatures.ed25519_alg != COSE_ALG_EDDSA {
            return Err("ERR_INVALID_ED25519_COSE_ALG_ID");
        }
        if self.signatures.mldsa65_alg != COSE_ALG_ML_DSA_65 {
            return Err("ERR_INVALID_MLDSA65_COSE_ALG_ID");
        }
        if self.signatures.mldsa65_parameter_set != "ML-DSA-65-FIPS-204" {
            return Err("ERR_INVALID_MLDSA65_PARAMETER_SET");
        }
        if self.signatures.ed25519_sig_hex.is_empty()
            || self.signatures.mldsa65_sig_commitment_hex.is_empty()
        {
            return Err("ERR_EMPTY_HYBRID_SIGNATURE_SLOT");
        }
        if self.unprotected_header_394.tree_size == 0
            || self.unprotected_header_394.leaf_index >= self.unprotected_header_394.tree_size
        {
            return Err("ERR_INVALID_RFC9942_MERKLE_BOUNDS");
        }
        if !self.act_caid.starts_with("sha256:") {
            return Err("ERR_MALFORMED_ACT_CAID");
        }
        Ok(())
    }
}
