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

/// Fetch a Task row by ID. Returns (id, tenant_id, status, intent).
pub async fn fetch_task(pool: &PgPool, task_id: Uuid) -> Result<Option<(Uuid, Uuid, String, String)>, sqlx::Error> {
    let row: Option<(Uuid, Uuid, String, String)> = sqlx::query_as(
        "SELECT id, tenant_id, status::text, intent FROM tasks WHERE id = $1"
    )
    .bind(task_id)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

/// Fetch a Persona row by ID. Returns (id, tenant_id, name, kind, is_frozen).
pub async fn fetch_persona(pool: &PgPool, persona_id: Uuid) -> Result<Option<(Uuid, Uuid, String, String, bool)>, sqlx::Error> {
    let row: Option<(Uuid, Uuid, String, String, bool)> = sqlx::query_as(
        "SELECT id, tenant_id, name, kind::text, is_frozen FROM personas WHERE id = $1"
    )
    .bind(persona_id)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

/// Fetch an IntentMandate row by ID. Returns (id, tenant_id, budget_limit, budget_spent, risk_class, allowed_tools).
pub async fn fetch_intent_mandate(
    pool: &PgPool,
    mandate_id: Uuid,
) -> Result<Option<(Uuid, Uuid, i64, i64, String, Vec<Uuid>)>, sqlx::Error> {
    let row: Option<(Uuid, Uuid, i64, i64, String, Vec<Uuid>)> = sqlx::query_as(
        "SELECT id, tenant_id, budget_limit, budget_spent, risk_class::text, allowed_tools \
         FROM intent_mandates WHERE id = $1"
    )
    .bind(mandate_id)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

/// Update a Task's status. Returns true if the update affected a row.
pub async fn update_task_status(
    pool: &PgPool,
    task_id: Uuid,
    new_status: &str,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE tasks SET status = $2::task_status, \
         completed_at = CASE WHEN $2 IN ('completed', 'failed') THEN NOW() ELSE completed_at END \
         WHERE id = $1"
    )
    .bind(task_id)
    .bind(new_status)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}

/// Freeze a Persona by setting is_frozen = true.
pub async fn freeze_persona(pool: &PgPool, persona_id: Uuid) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE personas SET is_frozen = TRUE WHERE id = $1"
    )
    .bind(persona_id)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}

/// Insert a PaymentMandate with a cryptographic signature. Returns its ID.
pub async fn insert_payment_mandate(
    pool: &PgPool,
    intent_mandate_id: Uuid,
    amount: i64,
    risk_class: &str,
    signature: &[u8],
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO payment_mandates (id, tenant_id, intent_mandate_id, amount, risk_class, status, cryptographic_signature) \
         VALUES ($1, $2, $3, $4, $5::risk_class, 'approved'::mandate_status, $6)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(intent_mandate_id)
    .bind(amount)
    .bind(risk_class)
    .bind(signature)
    .execute(pool)
    .await?;
    Ok(id)
}
