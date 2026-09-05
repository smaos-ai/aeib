use sqlx::PgPool;
use uuid::Uuid;

/// Check if a Persona has a specific access edge to a target, either directly
/// or through Team membership. Returns true if access is granted.
/// Implements spec section 4.4 ReBAC Evaluation Order.
pub async fn check_access(
    pool: &PgPool,
    persona_id: Uuid,
    target_id: Uuid,
    allow_type: &str,
    deny_type: &str,
    tenant_id: Uuid,
) -> Result<bool, sqlx::Error> {
    // Step 1: Check for any DENY edge (direct on persona, or on any team persona belongs to)
    let has_deny: bool = sqlx::query_scalar(
        "SELECT EXISTS(
            -- Direct deny on persona
            SELECT 1 FROM edges WHERE source_id = $1 AND target_id = $2 AND edge_type = $4::edge_type AND tenant_id = $5
            UNION ALL
            -- Deny via team: persona <- acts_as <- user -> member_of -> team -> deny edge
            SELECT 1 FROM edges deny_e
            JOIN edges member_e ON member_e.target_id = deny_e.source_id AND member_e.edge_type = 'member_of'
            JOIN edges acts_e ON acts_e.source_id = member_e.source_id AND acts_e.edge_type = 'acts_as'
            WHERE acts_e.target_id = $1
              AND deny_e.target_id = $2
              AND deny_e.edge_type = $4::edge_type
              AND deny_e.tenant_id = $5
        )"
    )
    .bind(persona_id)
    .bind(target_id)
    .bind(allow_type)
    .bind(deny_type)
    .bind(tenant_id)
    .fetch_one(pool)
    .await?;

    if has_deny {
        return Ok(false);
    }

    // Step 2: Check for any ALLOW edge
    let has_allow: bool = sqlx::query_scalar(
        "SELECT EXISTS(
            -- Direct allow on persona
            SELECT 1 FROM edges WHERE source_id = $1 AND target_id = $2 AND edge_type = $3::edge_type AND tenant_id = $5
            UNION ALL
            -- Allow via team
            SELECT 1 FROM edges allow_e
            JOIN edges member_e ON member_e.target_id = allow_e.source_id AND member_e.edge_type = 'member_of'
            JOIN edges acts_e ON acts_e.source_id = member_e.source_id AND acts_e.edge_type = 'acts_as'
            WHERE acts_e.target_id = $1
              AND allow_e.target_id = $2
              AND allow_e.edge_type = $3::edge_type
              AND allow_e.tenant_id = $5
        )"
    )
    .bind(persona_id)
    .bind(target_id)
    .bind(allow_type)
    .bind(deny_type)
    .bind(tenant_id)
    .fetch_one(pool)
    .await?;

    Ok(has_allow)
}
