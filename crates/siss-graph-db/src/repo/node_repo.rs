use sqlx::PgPool;
use uuid::Uuid;

/// Insert a Tenant and return its ID.
pub async fn insert_tenant(pool: &PgPool, name: &str) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO tenants (id, tenant_id, name) VALUES ($1, $1, $2)"
    )
    .bind(id)
    .bind(name)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Insert a User and return its ID.
pub async fn insert_user(pool: &PgPool, email: &str, tenant_id: Uuid) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO users (id, tenant_id, email) VALUES ($1, $2, $3)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(email)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Insert a Team and return its ID.
pub async fn insert_team(pool: &PgPool, name: &str, tenant_id: Uuid) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO teams (id, tenant_id, name) VALUES ($1, $2, $3)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(name)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Insert a Persona and return its ID.
pub async fn insert_persona(
    pool: &PgPool,
    name: &str,
    kind: &str,
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO personas (id, tenant_id, name, kind) VALUES ($1, $2, $3, $4::persona_kind)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(name)
    .bind(kind)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Insert a Tool and return its ID.
pub async fn insert_tool(
    pool: &PgPool,
    name: &str,
    tool_uri: &str,
    risk_class: &str,
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO tools (id, tenant_id, name, tool_uri, risk_class) VALUES ($1, $2, $3, $4, $5::risk_class)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(name)
    .bind(tool_uri)
    .bind(risk_class)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Insert an IntentMandate and return its ID.
pub async fn insert_intent_mandate(
    pool: &PgPool,
    budget_limit: i64,
    risk_class: &str,
    allowed_tools: &[Uuid],
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO intent_mandates (id, tenant_id, budget_limit, risk_class, allowed_tools) \
         VALUES ($1, $2, $3, $4::risk_class, $5)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(budget_limit)
    .bind(risk_class)
    .bind(allowed_tools)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Get the remaining budget for an IntentMandate.
pub async fn get_mandate_remaining(pool: &PgPool, mandate_id: Uuid) -> Result<i64, sqlx::Error> {
    let remaining: i64 = sqlx::query_scalar(
        "SELECT budget_limit - budget_spent FROM intent_mandates WHERE id = $1"
    )
    .bind(mandate_id)
    .fetch_one(pool)
    .await?;
    Ok(remaining)
}
