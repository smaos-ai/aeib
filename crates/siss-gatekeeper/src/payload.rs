use sha2::{Digest, Sha256};
use uuid::Uuid;

/// Build the deterministic 48-byte payload for signing a PaymentMandate.
/// Format: task_id (16 bytes) || intent_mandate_id (16 bytes) || amount (8 bytes BE) || timestamp (8 bytes BE)
pub fn build_signing_payload(
    task_id: Uuid,
    intent_mandate_id: Uuid,
    amount: i64,
    timestamp_epoch_secs: i64,
) -> Vec<u8> {
    let mut payload = Vec::with_capacity(48);
    payload.extend_from_slice(task_id.as_bytes());
    payload.extend_from_slice(intent_mandate_id.as_bytes());
    payload.extend_from_slice(&amount.to_be_bytes());
    payload.extend_from_slice(&timestamp_epoch_secs.to_be_bytes());
    payload
}

/// Build the deterministic 96-byte payload for signing an ExecutionMandate (Phase 41).
/// Format: mandate_id (16B) || intent_mandate_id (16B) || task_id (16B) || amount (8B BE)
///         || sha256(nonce) (32B) || created_at_epoch (8B BE)
pub fn build_execution_mandate_payload(
    mandate_id: Uuid,
    intent_mandate_id: Uuid,
    task_id: Uuid,
    amount: i64,
    nonce: &[u8],
    created_at_epoch: i64,
) -> Vec<u8> {
    let mut hasher = Sha256::new();
    hasher.update(nonce);
    let nonce_hash = hasher.finalize();

    let mut payload = Vec::with_capacity(96);
    payload.extend_from_slice(mandate_id.as_bytes());
    payload.extend_from_slice(intent_mandate_id.as_bytes());
    payload.extend_from_slice(task_id.as_bytes());
    payload.extend_from_slice(&amount.to_be_bytes());
    payload.extend_from_slice(&nonce_hash[..]);
    payload.extend_from_slice(&created_at_epoch.to_be_bytes());
    payload
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_payload_is_48_bytes() {
        let payload = build_signing_payload(Uuid::nil(), Uuid::nil(), 1000, 1000000);
        assert_eq!(payload.len(), 48);
    }

    #[test]
    fn test_payload_is_deterministic() {
        let task = Uuid::new_v4();
        let mandate = Uuid::new_v4();
        let p1 = build_signing_payload(task, mandate, 500, 12345);
        let p2 = build_signing_payload(task, mandate, 500, 12345);
        assert_eq!(p1, p2);
    }

    #[test]
    fn test_different_amounts_produce_different_payloads() {
        let task = Uuid::new_v4();
        let mandate = Uuid::new_v4();
        let p1 = build_signing_payload(task, mandate, 500, 12345);
        let p2 = build_signing_payload(task, mandate, 501, 12345);
        assert_ne!(p1, p2);
    }
}
