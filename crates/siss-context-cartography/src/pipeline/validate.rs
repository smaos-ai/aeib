use sqlx::PgPool;
use uuid::Uuid;

use crate::types::CartographyError;

pub async fn validate(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
) -> Result<(), CartographyError> {
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await
        .map_err(|e| CartographyError::DatabaseError { message: e.to_string() })?
        .ok_or(CartographyError::TaskNotFound { task_id })?;

    let (_id, task_tenant, _status, _intent) = task_row;
    if task_tenant != tenant_id {
        return Err(CartographyError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    let persona_row = siss_graph_db::repo::node_repo::fetch_persona(pool, persona_id)
        .await
        .map_err(|e| CartographyError::DatabaseError { message: e.to_string() })?
        .ok_or(CartographyError::PersonaNotFound { persona_id })?;

    let (_id, persona_tenant, _name, _kind, _is_frozen) = persona_row;
    if persona_tenant != tenant_id {
        return Err(CartographyError::TenantViolation {
            source_tenant: persona_tenant,
            target_tenant: tenant_id,
        });
    }

    Ok(())
}
