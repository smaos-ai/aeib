use sqlx::PgPool;
use uuid::Uuid;

/// Atomically debit an IntentMandate's budget. Uses a CHECK constraint
/// in the database to enforce budget_spent <= budget_limit.
/// Returns the new budget_spent on success.
pub async fn debit_mandate(
    pool: &PgPool,
    mandate_id: Uuid,
    amount: i64,
) -> Result<i64, sqlx::Error> {
    let new_spent: i64 = sqlx::query_scalar(
        "UPDATE intent_mandates \
         SET budget_spent = budget_spent + $2 \
         WHERE id = $1 \
         RETURNING budget_spent"
    )
    .bind(mandate_id)
    .bind(amount)
    .fetch_one(pool)
    .await?;
    Ok(new_spent)
}

/// Create a PaymentMandate linked to an IntentMandate.
pub async fn create_payment_mandate(
    pool: &PgPool,
    intent_mandate_id: Uuid,
    amount: i64,
    risk_class: &str,
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO payment_mandates (id, tenant_id, intent_mandate_id, amount, risk_class) \
         VALUES ($1, $2, $3, $4, $5::risk_class)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(intent_mandate_id)
    .bind(amount)
    .bind(risk_class)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Create an immutable PaymentReceipt.
pub async fn create_payment_receipt(
    pool: &PgPool,
    payment_mandate_id: Uuid,
    amount: i64,
    signature: &[u8],
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO payment_receipts (id, tenant_id, payment_mandate_id, amount, cryptographic_signature) \
         VALUES ($1, $2, $3, $4, $5)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(payment_mandate_id)
    .bind(amount)
    .bind(signature)
    .execute(pool)
    .await?;
    Ok(id)
}
