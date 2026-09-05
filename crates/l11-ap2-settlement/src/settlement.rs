use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum SettlementStatus {
    Initiated,
    CommitmentExchanged,
    Committed,
    Aborted,
}

impl SettlementStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Initiated => "initiated",
            Self::CommitmentExchanged => "commitment_exchanged",
            Self::Committed => "committed",
            Self::Aborted => "aborted",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settlement {
    pub id: Uuid,
    pub from_org_did: String,
    pub to_org_did: String,
    pub amount: Decimal,
    pub currency: String,
    pub status: SettlementStatus,
    pub created_at: DateTime<Utc>,
    pub committed_at: Option<DateTime<Utc>>,
    pub aborted_at: Option<DateTime<Utc>>,
    pub ledger_hash: Option<String>,
    pub nonce: String,
}

impl Settlement {
    pub fn new(
        from_org_did: String,
        to_org_did: String,
        amount: Decimal,
        currency: String,
    ) -> Self {
        let nonce = uuid::Uuid::new_v4().to_string();
        Self {
            id: Uuid::new_v4(),
            from_org_did,
            to_org_did,
            amount,
            currency,
            status: SettlementStatus::Initiated,
            created_at: Utc::now(),
            committed_at: None,
            aborted_at: None,
            ledger_hash: None,
            nonce,
        }
    }

    pub fn initiate(&mut self) {
        self.status = SettlementStatus::Initiated;
    }

    pub fn exchange_commitment(&mut self) {
        if self.status == SettlementStatus::Initiated {
            self.status = SettlementStatus::CommitmentExchanged;
        }
    }

    pub fn commit(&mut self, ledger_hash: String) {
        if self.status == SettlementStatus::CommitmentExchanged {
            self.status = SettlementStatus::Committed;
            self.committed_at = Some(Utc::now());
            self.ledger_hash = Some(ledger_hash);
        }
    }

    pub fn abort(&mut self) {
        self.status = SettlementStatus::Aborted;
        self.aborted_at = Some(Utc::now());
    }

    pub fn can_commit(&self) -> bool {
        self.status == SettlementStatus::CommitmentExchanged
    }

    pub fn is_complete(&self) -> bool {
        self.status == SettlementStatus::Committed
    }

    pub fn compute_commitment_hash(&self) -> String {
        use sha2::{Digest, Sha256};
        let data = format!(
            "{}||{}||{}||{}",
            self.id, self.amount, self.nonce, self.created_at.timestamp()
        );
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        hex::encode(hasher.finalize())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementSignature {
    pub id: Uuid,
    pub settlement_id: Uuid,
    pub signer_did: String,
    pub signature_bytes: String,
    pub signed_at: DateTime<Utc>,
}

impl SettlementSignature {
    pub fn new(
        settlement_id: Uuid,
        signer_did: String,
        signature_bytes: String,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            settlement_id,
            signer_did,
            signature_bytes,
            signed_at: Utc::now(),
        }
    }
}
