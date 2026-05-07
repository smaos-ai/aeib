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
