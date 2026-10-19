//! crates/aeib-data-plane/tests/test_scitt_merkle_tree.rs
//! ============================================================================
//! Verification tests for RFC 9162 / RFC 9942 SCITT Merkle Tree & Inclusion Proofs.
//! Tests domain separation, multi-leaf audit paths, and tamper rejection.
//! ============================================================================

use aeib_data_plane::scitt::ScittMerkleTree;

#[test]
fn test_scitt_merkle_tree_single_leaf() {
    let mut tree = ScittMerkleTree::new();
    let entry = b"aeib:receipt:single";
    let leaf_hash = ScittMerkleTree::hash_leaf(entry);

    let idx = tree.add_entry(entry);
    assert_eq!(idx, 0);
    assert_eq!(tree.tree_size(), 1);

    let root = tree.root_hash();
    assert_eq!(root, leaf_hash);

    let proof = tree.inclusion_proof(0).expect("Proof must exist");
    assert_eq!(proof.leaf_index, 0);
    assert_eq!(proof.tree_size, 1);
    assert!(proof.audit_path.is_empty());
    assert!(proof.verify(&leaf_hash, &root));
}

#[test]
fn test_scitt_merkle_tree_four_leaves_inclusion_and_falsification() {
    let mut tree = ScittMerkleTree::new();
    let mut leaf_hashes = Vec::new();

    for i in 0..4 {
        let entry = format!("aeib:receipt:slot:{}", i);
        leaf_hashes.push(ScittMerkleTree::hash_leaf(entry.as_bytes()));
        tree.add_entry(entry.as_bytes());
    }

    assert_eq!(tree.tree_size(), 4);
    let root = tree.root_hash();

    // Verify all 4 inclusion proofs
    for i in 0..4 {
        let proof = tree.inclusion_proof(i).expect("Proof must exist");
        assert_eq!(proof.leaf_index, i);
        assert_eq!(proof.tree_size, 4);
        assert_eq!(proof.audit_path.len(), 2);
        assert!(
            proof.verify(&leaf_hashes[i], &root),
            "Proof failed for leaf {}",
            i
        );

        // Falsification: tampered leaf must fail verification
        let mut tampered_leaf = leaf_hashes[i];
        tampered_leaf[0] ^= 0xFF;
        assert!(
            !proof.verify(&tampered_leaf, &root),
            "Tampered leaf must be rejected"
        );

        // Falsification: tampered root must fail verification
        let mut tampered_root = root;
        tampered_root[0] ^= 0xFF;
        assert!(
            !proof.verify(&leaf_hashes[i], &tampered_root),
            "Tampered root must be rejected"
        );
    }
}

#[test]
fn test_scitt_merkle_tree_odd_leaves_inclusion() {
    let mut tree = ScittMerkleTree::new();
    let mut leaf_hashes = Vec::new();

    // 7 leaves (non-power-of-two)
    for i in 0..7 {
        let entry = format!("aeib:receipt:odd:{}", i);
        leaf_hashes.push(ScittMerkleTree::hash_leaf(entry.as_bytes()));
        tree.add_entry(entry.as_bytes());
    }

    assert_eq!(tree.tree_size(), 7);
    let root = tree.root_hash();

    for i in 0..7 {
        let proof = tree.inclusion_proof(i).expect("Proof must exist");
        assert_eq!(proof.leaf_index, i);
        assert_eq!(proof.tree_size, 7);
        assert!(
            proof.verify(&leaf_hashes[i], &root),
            "Proof failed for odd tree leaf {}",
            i
        );
    }
}
