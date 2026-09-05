use sqlx::PgPool;
use uuid::Uuid;

use crate::types::{Invoice, License, LicenseError};

pub async fn insert_license(pool: &PgPool, license: &License) -> Result<Uuid, LicenseError> {
    sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO licenses (id, customer_id, license_key, sku, expires_at, revoked, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         RETURNING id",
    )
    .bind(license.id)
    .bind(license.customer_id)
    .bind(&license.key)
    .bind(license.sku.as_str())
    .bind(license.expires_at)
    .bind(license.revoked)
    .bind(license.created_at)
    .fetch_one(pool)
    .await
    .map_err(|e| LicenseError::DatabaseError(e.to_string()))
}

pub async fn fetch_license_by_key(
    pool: &PgPool,
    key: &str,
) -> Result<Option<License>, LicenseError> {
    let row = sqlx::query_as::<_, (Uuid, Uuid, String, String, sqlx::types::chrono::DateTime<sqlx::types::chrono::Utc>, bool, sqlx::types::chrono::DateTime<sqlx::types::chrono::Utc>)>(
        "SELECT id, customer_id, license_key, sku, expires_at, revoked, created_at
         FROM licenses
         WHERE license_key = $1",
    )
    .bind(key)
    .fetch_optional(pool)
    .await
    .map_err(|e| LicenseError::DatabaseError(e.to_string()))?;

    Ok(row.map(|(id, customer_id, license_key, sku, expires_at, revoked, created_at)| {
        License {
            id,
            key: license_key,
            customer_id,
            sku: crate::types::Sku::from_str(&sku).unwrap_or(crate::types::Sku::Starter),
            expires_at,
            revoked,
            created_at,
        }
    }))
}

pub async fn revoke_license(pool: &PgPool, customer_id: Uuid) -> Result<(), LicenseError> {
    sqlx::query("UPDATE licenses SET revoked = true WHERE customer_id = $1")
        .bind(customer_id)
        .execute(pool)
        .await
        .map_err(|e| LicenseError::DatabaseError(e.to_string()))?;

    Ok(())
}

pub async fn fetch_invoices(
    pool: &PgPool,
    customer_id: Uuid,
) -> Result<Vec<Invoice>, LicenseError> {
    let rows = sqlx::query_as::<_, (Uuid, Uuid, i64, String, String, sqlx::types::chrono::DateTime<sqlx::types::chrono::Utc>)>(
        "SELECT id, customer_id, amount_cents, sku, status, created_at
         FROM invoices
         WHERE customer_id = $1
         ORDER BY created_at DESC",
    )
    .bind(customer_id)
    .fetch_all(pool)
    .await
    .map_err(|e| LicenseError::DatabaseError(e.to_string()))?;

    Ok(rows
        .into_iter()
        .map(|(id, cid, amount_cents, sku, status, created_at)| Invoice {
            id,
            customer_id: cid,
            amount_cents,
            sku: crate::types::Sku::from_str(&sku).unwrap_or(crate::types::Sku::Starter),
            status,
            created_at,
        })
        .collect())
}

#[cfg(test)]
mod tests {
    #[tokio::test]
    #[ignore] // requires database
    async fn test_insert_license() {
        // This test requires a running database
        // Skipped in CI/CD
    }

    #[tokio::test]
    #[ignore]
    async fn test_fetch_license_by_key() {}

    #[tokio::test]
    #[ignore]
    async fn test_revoke_license() {}

    #[tokio::test]
    #[ignore]
    async fn test_fetch_invoices() {}
}
