pub mod replication;
pub mod failover;
pub mod sync;
pub mod reconciliation;
pub mod health_check;
pub mod errors;

pub use replication::{MultiRegionReplicator, ReplicationEvent, ReplicationState};
pub use failover::{FailoverManager, FailoverDecision};
pub use sync::{CapsuleSyncManager, SyncStatus};
pub use reconciliation::{ReconciliationManager, ReconciliationStrategy};
pub use health_check::{HealthChecker, RegionHealth, HealthStatus};
pub use errors::{MultiRegionError, MultiRegionResult};
