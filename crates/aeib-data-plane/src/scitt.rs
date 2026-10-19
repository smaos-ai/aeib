//! crates/aeib-data-plane/src/scitt.rs
//! ============================================================================
//! AEIB IETF SCITT (RFC 9942 / RFC 9943) Binary Merkle Tree & Transparent
//! Statement Receipt Generator.
//!
//! Standards Grounding:
//! - RFC 9943: Supply Chain Integrity, Transparency, and Trust (SCITT) Architecture
//! - RFC 9942: Merkle Tree Receipts in COSE
//! - RFC 9162: Certificate Transparency Version 2.0 (domain separation 0x00/0x01)
//! - IANA COSE Header Parameters:
//!     * 394: receipts (unprotected header on Signed Statement)
//!     * 395: vds (Verifiable Data Structure algorithm: 1 = RFC9162_SHA256)
//!     * 396: vdp (Verifiable Data Structure Proof)
//! ============================================================================

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;

pub const COSE_HEADER_RECEIPTS: i64 = 394;
pub const COSE_HEADER_VDS: i64 = 395;
pub const COSE_HEADER_VDP: i64 = 396;
pub const VDS_RFC9162_SHA256: i64 = 1;

/// RFC 9162 domain-separated binary SHA-256 Merkle tree for SCITT transparency logging.
pub struct ScittMerkleTree {
    leaves: Vec<[u8; 32]>,
}

impl ScittMerkleTree {
    pub fn new() -> Self {
        Self { leaves: Vec::new() }
    }

    /// Computes RFC 9162 leaf hash: SHA-256(0x00 || entry_bytes).
    pub fn hash_leaf(entry_bytes: &[u8]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update([0x00]);
        hasher.update(entry_bytes);
        let result = hasher.finalize();
        let mut out = [0u8; 32];
        out.copy_from_slice(&result);
        out
    }

    /// Computes RFC 9162 internal node hash: SHA-256(0x01 || left || right).
    pub fn hash_node(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update([0x01]);
        hasher.update(left);
        hasher.update(right);
        let result = hasher.finalize();
        let mut out = [0u8; 32];
        out.copy_from_slice(&result);
        out
    }

    /// Appends a new raw entry bytes to the tree, returning its leaf index.
    pub fn add_entry(&mut self, entry_bytes: &[u8]) -> usize {
        let leaf_hash = Self::hash_leaf(entry_bytes);
        let idx = self.leaves.len();
        self.leaves.push(leaf_hash);
        idx
    }

    /// Appends an already-computed leaf hash.
    pub fn add_leaf_hash(&mut self, leaf_hash: [u8; 32]) -> usize {
        let idx = self.leaves.len();
        self.leaves.push(leaf_hash);
        idx
    }

    pub fn tree_size(&self) -> usize {
        self.leaves.len()
    }

    /// Computes the root hash of the tree. If empty, returns 32 zero bytes.
    pub fn root_hash(&self) -> [u8; 32] {
        if self.leaves.is_empty() {
            return [0u8; 32];
        }
        Self::compute_sub_root(&self.leaves)
    }

    fn compute_sub_root(slice: &[[u8; 32]]) -> [u8; 32] {
        let n = slice.len();
        if n == 1 {
            return slice[0];
        }
        let k = largest_power_of_two_less_than(n);
        let left = Self::compute_sub_root(&slice[..k]);
        let right = Self::compute_sub_root(&slice[k..]);
        Self::hash_node(&left, &right)
    }

    /// Generates an RFC 9162 inclusion proof for leaf at `leaf_index`.
    pub fn inclusion_proof(&self, leaf_index: usize) -> Option<MerkleInclusionProof> {
        let n = self.leaves.len();
        if leaf_index >= n {
            return None;
        }

        let mut audit_path = Vec::new();
        Self::build_audit_path(&self.leaves, leaf_index, &mut audit_path);

        Some(MerkleInclusionProof {
            leaf_index,
            tree_size: n,
            audit_path,
            root_hash: self.root_hash(),
        })
    }

    fn build_audit_path(slice: &[[u8; 32]], m: usize, path: &mut Vec<[u8; 32]>) {
        let n = slice.len();
        if n <= 1 {
            return;
        }
        let k = largest_power_of_two_less_than(n);
        if m < k {
            Self::build_audit_path(&slice[..k], m, path);
            path.push(Self::compute_sub_root(&slice[k..]));
        } else {
            Self::build_audit_path(&slice[k..], m - k, path);
            path.push(Self::compute_sub_root(&slice[..k]));
        }
    }
}

/// Computes the largest power of 2 strictly less than n (for n >= 2).
fn largest_power_of_two_less_than(n: usize) -> usize {
    debug_assert!(n >= 2);
    let mut p = 1;
    while p * 2 < n {
        p *= 2;
    }
    p
}

/// An RFC 9162 audit proof showing that a leaf is included in a Merkle root.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MerkleInclusionProof {
    pub leaf_index: usize,
    pub tree_size: usize,
    pub audit_path: Vec<[u8; 32]>,
    pub root_hash: [u8; 32],
}

impl MerkleInclusionProof {
    /// Verifies that `leaf_hash` is present in `expected_root` using this proof
    /// per RFC 9162 Section 2.1.3.
    pub fn verify(&self, leaf_hash: &[u8; 32], expected_root: &[u8; 32]) -> bool {
        if self.leaf_index >= self.tree_size || self.tree_size == 0 {
            return false;
        }
        if self.tree_size == 1 {
            return self.audit_path.is_empty()
                && bool::from(leaf_hash.ct_eq(expected_root))
                && bool::from(self.root_hash.ct_eq(expected_root));
        }

        // Reconstruct top-down split direction steps per RFC 9162 Section 2.1.3
        let mut steps_is_right_sibling = Vec::new();
        let mut m = self.leaf_index;
        let mut n = self.tree_size;

        while n > 1 {
            let k = largest_power_of_two_less_than(n);
            if m < k {
                steps_is_right_sibling.push(true);
                n = k;
            } else {
                steps_is_right_sibling.push(false);
                m -= k;
                n -= k;
            }
        }

        if self.audit_path.len() != steps_is_right_sibling.len() {
            return false;
        }

        let mut current_hash = *leaf_hash;
        for (sibling, is_right) in self
            .audit_path
            .iter()
            .zip(steps_is_right_sibling.into_iter().rev())
        {
            if is_right {
                current_hash = ScittMerkleTree::hash_node(&current_hash, sibling);
            } else {
                current_hash = ScittMerkleTree::hash_node(sibling, &current_hash);
            }
        }

        let root_matches_expected = current_hash.ct_eq(expected_root);
        let proof_matches_expected = self.root_hash.ct_eq(expected_root);

        bool::from(root_matches_expected & proof_matches_expected)
    }
}
