//! L8: Immutable proof layer with AP2 ledger + PQC signatures
//! agentacct work receipts + unlazy gates + AP2 ledger + KMS signing

pub mod proof;

pub use proof::{ProofLayer, WorkReceipt, LedgerEntry};
