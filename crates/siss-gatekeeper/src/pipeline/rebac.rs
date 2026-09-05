use sqlx::PgPool;
use uuid::Uuid;

use crate::types::GatekeeperError;

/// Pipeline Step 2: Verify the Persona has CAN_EXECUTE access to every requested tool.
pub async fn check_tool_access(
    pool: &PgPool,
    persona_id: Uuid,
    requested_tools: &[Uuid],
    tenant_id: Uuid,
) -> Result<(), GatekeeperError> {
    for &tool_id in requested_tools {
        let has_access = siss_graph_db::repo::rebac_repo::check_access(
            pool,
            persona_id,
            tool_id,
            "can_execute",
            "deny_execute",
            tenant_id,
        )
        .await?;

        if !has_access {
            return Err(GatekeeperError::AccessDenied { tool_id });
        }
    }
    Ok(())
}
