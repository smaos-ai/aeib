use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::execution::HardwareTarget;

use crate::types::RouterError;

/// Convert HardwareTarget enum to the database string representation.
fn hardware_target_to_str(target: HardwareTarget) -> &'static str {
    match target {
        HardwareTarget::LocalMlx => "local_mlx",
        HardwareTarget::RemoteFrontier => "remote_frontier",
        HardwareTarget::Hybrid => "hybrid",
    }
}

/// Pipeline Step 2: Update hardware_target in DB and transition Task to routing.
pub async fn apply_routing_decision(
    pool: &PgPool,
    task_id: Uuid,
    hardware_target: HardwareTarget,
) -> Result<(), RouterError> {
    siss_graph_db::repo::node_repo::update_task_hardware_target(
        pool,
        task_id,
        hardware_target_to_str(hardware_target),
    )
    .await?;

    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "routing")
        .await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardware_target_to_str() {
        assert_eq!(hardware_target_to_str(HardwareTarget::LocalMlx), "local_mlx");
        assert_eq!(hardware_target_to_str(HardwareTarget::RemoteFrontier), "remote_frontier");
        assert_eq!(hardware_target_to_str(HardwareTarget::Hybrid), "hybrid");
    }
}
