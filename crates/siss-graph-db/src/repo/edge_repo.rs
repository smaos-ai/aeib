use sqlx::PgPool;
use uuid::Uuid;

/// Insert an edge into the unified edges table.
pub async fn insert_edge(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    edge_type: &str,
    tenant_id: Uuid,
    metadata: serde_json::Value,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO edges (id, source_id, target_id, edge_type, tenant_id, metadata) \
         VALUES ($1, $2, $3, $4::edge_type, $5, $6)"
    )
    .bind(id)
    .bind(source_id)
    .bind(target_id)
    .bind(edge_type)
    .bind(tenant_id)
    .bind(metadata)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Find all edges of a given type from a source node within a tenant.
pub async fn find_edges_from(
    pool: &PgPool,
    source_id: Uuid,
    edge_type: &str,
    tenant_id: Uuid,
) -> Result<Vec<(Uuid, Uuid, Uuid)>, sqlx::Error> {
    let rows: Vec<(Uuid, Uuid, Uuid)> = sqlx::query_as(
        "SELECT id, source_id, target_id FROM edges \
         WHERE source_id = $1 AND edge_type = $2::edge_type AND tenant_id = $3"
    )
    .bind(source_id)
    .bind(edge_type)
    .bind(tenant_id)
    .fetch_all(pool)
    .await?;
    Ok(rows)
}

/// Find all edges of a given type pointing to a target node within a tenant.
pub async fn find_edges_to(
    pool: &PgPool,
    target_id: Uuid,
    edge_type: &str,
    tenant_id: Uuid,
) -> Result<Vec<(Uuid, Uuid, Uuid)>, sqlx::Error> {
    let rows: Vec<(Uuid, Uuid, Uuid)> = sqlx::query_as(
        "SELECT id, source_id, target_id FROM edges \
         WHERE target_id = $1 AND edge_type = $2::edge_type AND tenant_id = $3"
    )
    .bind(target_id)
    .bind(edge_type)
    .bind(tenant_id)
    .fetch_all(pool)
    .await?;
    Ok(rows)
}
