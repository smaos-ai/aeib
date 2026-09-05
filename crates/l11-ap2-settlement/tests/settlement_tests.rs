use l11_ap2_settlement::{Settlement, SettlementStatus, AtomicSwap, SettlementLedger};
use rust_decimal::Decimal;

#[test]
fn test_settlement_creation() {
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    assert_eq!(settlement.from_org_did, "did:smaos:org-a");
    assert_eq!(settlement.to_org_did, "did:smaos:org-b");
    assert_eq!(settlement.amount, Decimal::from(1000));
    assert_eq!(settlement.currency, "EUR");
    assert_eq!(settlement.status, SettlementStatus::Initiated);
}

#[test]
fn test_settlement_status_transitions() {
    let mut settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(500),
        "USD".to_string(),
    );

    assert_eq!(settlement.status, SettlementStatus::Initiated);

    settlement.exchange_commitment();
    assert_eq!(settlement.status, SettlementStatus::CommitmentExchanged);

    settlement.commit("ledger_hash_123".to_string());
    assert_eq!(settlement.status, SettlementStatus::Committed);
    assert!(settlement.committed_at.is_some());
    assert_eq!(settlement.ledger_hash, Some("ledger_hash_123".to_string()));
}

#[test]
fn test_settlement_abort() {
    let mut settlement = Settlement::new(
        "did:smaos:org-x".to_string(),
        "did:smaos:org-y".to_string(),
        Decimal::from(250),
        "GBP".to_string(),
    );

    settlement.abort();
    assert_eq!(settlement.status, SettlementStatus::Aborted);
    assert!(settlement.aborted_at.is_some());
}

#[test]
fn test_settlement_commitment_hash() {
    let settlement1 = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    let hash1 = settlement1.compute_commitment_hash();
    assert!(!hash1.is_empty());
    assert_eq!(hash1.len(), 64); // SHA256 hex = 64 chars

    // Same settlement should produce same hash
    let settlement2 = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );
    // Different settlement (different ID) = different hash
    let hash2 = settlement2.compute_commitment_hash();
    assert_ne!(hash1, hash2);
}

#[test]
fn test_atomic_swap_create_commitment() {
    let mut swap = AtomicSwap::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    let commitment = swap.create_commitment(&settlement).unwrap();
    assert!(!commitment.is_empty());
}

#[test]
fn test_atomic_swap_duplicate_commitment_rejected() {
    let mut swap = AtomicSwap::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(500),
        "USD".to_string(),
    );

    swap.create_commitment(&settlement).unwrap();
    let result = swap.create_commitment(&settlement);

    assert!(result.is_err());
}

#[test]
fn test_atomic_swap_verify_commitment() {
    let mut swap = AtomicSwap::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    let commitment = swap.create_commitment(&settlement).unwrap();
    let verified = swap.verify_commitment(settlement.id, &commitment).unwrap();

    assert!(verified);
}

#[test]
fn test_atomic_swap_invalid_commitment() {
    let mut swap = AtomicSwap::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    swap.create_commitment(&settlement).unwrap();

    let invalid_commitment = "invalid_hash_xxxxx";
    let verified = swap.verify_commitment(settlement.id, invalid_commitment).unwrap();
    assert!(!verified);
}

#[test]
fn test_atomic_swap_add_signatures() {
    use l11_ap2_settlement::settlement::SettlementSignature;

    let mut swap = AtomicSwap::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    swap.create_commitment(&settlement).unwrap();

    let sig1 = SettlementSignature::new(
        settlement.id,
        "did:smaos:org-a".to_string(),
        "sig_bytes_001".to_string(),
    );

    swap.add_signature(settlement.id, sig1).unwrap();

    let sigs = swap.get_signatures(settlement.id).unwrap();
    assert_eq!(sigs.len(), 1);
}

#[test]
fn test_atomic_swap_can_commit() {
    use l11_ap2_settlement::settlement::SettlementSignature;

    let mut swap = AtomicSwap::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    swap.create_commitment(&settlement).unwrap();

    // Need 2 signatures to commit
    let sig1 = SettlementSignature::new(
        settlement.id,
        "did:smaos:org-a".to_string(),
        "sig1".to_string(),
    );
    let sig2 = SettlementSignature::new(
        settlement.id,
        "did:smaos:org-b".to_string(),
        "sig2".to_string(),
    );

    swap.add_signature(settlement.id, sig1).unwrap();
    swap.add_signature(settlement.id, sig2).unwrap();

    let can_commit = swap.can_commit_settlement(settlement.id).unwrap();
    assert!(can_commit);
}

#[test]
fn test_settlement_ledger_record_initiated() {
    let mut ledger = SettlementLedger::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    let digest = ledger.record_settlement_initiated(&settlement).unwrap();
    assert!(!digest.is_empty());

    let status = ledger.get_settlement_status(settlement.id).unwrap();
    assert_eq!(status, "initiated");
}

#[test]
fn test_settlement_ledger_record_confirmed() {
    let mut ledger = SettlementLedger::new();
    let mut settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    ledger.record_settlement_initiated(&settlement).unwrap();
    ledger.record_settlement_confirmed(&settlement, "hash_123").unwrap();

    let status = ledger.get_settlement_status(settlement.id).unwrap();
    assert_eq!(status, "confirmed");

    let history = ledger.get_settlement_history(settlement.id).unwrap();
    assert_eq!(history.len(), 2);
}

#[test]
fn test_settlement_ledger_immutability() {
    let mut ledger = SettlementLedger::new();
    let settlement = Settlement::new(
        "did:smaos:org-a".to_string(),
        "did:smaos:org-b".to_string(),
        Decimal::from(1000),
        "EUR".to_string(),
    );

    let digest1 = ledger.record_settlement_initiated(&settlement).unwrap();
    let verified = ledger.verify_ledger_entry(settlement.id, &digest1).unwrap();
    assert!(verified);

    let invalid_digest = "invalid_digest";
    let verified_invalid = ledger.verify_ledger_entry(settlement.id, invalid_digest).unwrap();
    assert!(!verified_invalid);
}
