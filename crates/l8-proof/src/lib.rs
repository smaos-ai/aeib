//! L8: Immutable proof layer with AP2 ledger + PQC signatures
//! agentacct work receipts + unlazy gates + AP2 ledger + KMS signing

pub mod error;
pub mod proof;
pub mod l8_egress_ledger;

pub use error::{L8AuditEntry, L8Error};
pub use proof::{LedgerEntry, ProofLayer, WorkReceipt};
pub use l8_egress_ledger::{EgressLedger, EgressLedgerEntry, EgressDecision, KmsSignature};
