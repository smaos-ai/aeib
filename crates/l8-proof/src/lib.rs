//! L8: Immutable proof layer with AP2 ledger + PQC signatures
//! agentacct work receipts + unlazy gates + AP2 ledger + KMS signing

pub mod agentacct;
pub mod ap2_ledger;
pub mod error;
pub mod integration;
pub mod kms;
pub mod l8_egress_ledger;
pub mod proof;

pub use agentacct::{AgentacctStore, AgentacctWorkReceipt};
pub use ap2_ledger::{AP2Ledger, AP2LedgerEntry, AP2MerkleRoot};
pub use error::{L8AuditEntry, L8Error};
pub use integration::{PipelineStage, ProofHarness, WorkflowContext};
pub use kms::{KmsKey, KmsVault};
pub use l8_egress_ledger::{EgressDecision, EgressLedger, EgressLedgerEntry, KmsSignature};
pub use proof::{LedgerEntry, ProofLayer, WorkReceipt};
