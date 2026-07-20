pub mod attestation;
pub mod mandate;
pub mod dual_loop;
pub mod exec_log;
pub mod archival;
pub mod monitoring;

pub use attestation::{SovereignKeypair, AttestationError, sha256};
pub use mandate::{Mandate, MandateStore, MandateError, DashMapStore};
pub use dual_loop::{Layer0Gate, CapabilityToken, GateError, GateResult};
pub use exec_log::{ExecLogEntry, InMemoryAuditLog, ExecLogError};
pub use archival::{ColdStorageArchiver, ArchiveConfig, ArchiveStats, ArchiveError};
pub use monitoring::{MerkleChainMonitor, HealthStatus, ChainVerification, TamperAlerts, TamperAlert};
