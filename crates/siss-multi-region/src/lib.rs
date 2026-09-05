pub mod errors;
pub mod failover;
pub mod health_check;
pub mod reconciliation;
pub mod replication;
pub mod sync;

pub use errors::{MultiRegionError, MultiRegionResult};
pub use failover::{FailoverDecision, FailoverManager};
pub use health_check::{HealthChecker, HealthStatus, RegionHealth};
pub use reconciliation::{ReconciliationManager, ReconciliationStrategy};
pub use replication::{MultiRegionReplicator, ReplicationEvent, ReplicationState};
pub use sync::{CapsuleSyncManager, SyncStatus};
