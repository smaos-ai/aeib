#[cfg(feature = "axum")]
use axum::{
    extract::Path,
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::types::{Invoice, LicenseError, Sku, VerifiedLicense};

#[cfg(feature = "axum")]
#[derive(Debug, Deserialize)]
pub struct CheckoutRequest {
    pub customer_id: Uuid,
    pub sku: String,
}

#[cfg(feature = "axum")]
#[derive(Debug, Serialize)]
pub struct CheckoutResponse {
    pub session_id: String,
    pub url: String,
    pub amount_cents: i64,
}

#[cfg(feature = "axum")]
#[derive(Debug, Deserialize)]
pub struct VerifyRequest {
    pub customer_id: Uuid,
}

#[cfg(feature = "axum")]
#[derive(Debug, Serialize)]
pub struct VerifyResponse {
    pub valid: bool,
    pub sku: String,
    pub expires_at: String,
}

#[cfg(feature = "axum")]
#[derive(Debug, Deserialize)]
pub struct UsageRequest {
    pub customer_id: Uuid,
}

#[cfg(feature = "axum")]
#[derive(Debug, Serialize)]
pub struct UsageResponse {
    pub calls_recorded: u64,
    pub remaining_quota: u64,
}

#[cfg(feature = "axum")]
#[derive(Debug, Deserialize)]
pub struct GenerateRequest {
    pub customer_id: Uuid,
    pub sku: String,
    pub expires_at: String,
}

#[cfg(feature = "axum")]
#[derive(Debug, Serialize)]
pub struct GenerateResponse {
    pub license_key: String,
}

#[cfg(feature = "axum")]
#[derive(Debug, Deserialize)]
pub struct WebhookPayload {
    pub event_type: String,
    pub data: serde_json::Value,
}

#[cfg(feature = "axum")]
#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
    pub status_code: u16,
}

impl IntoResponse for LicenseError {
    fn into_response(self) -> axum::response::Response {
        let (status, error_msg) = match self {
            LicenseError::Expired => (StatusCode::PAYMENT_REQUIRED, "License expired"),
            LicenseError::Revoked => (StatusCode::PAYMENT_REQUIRED, "License revoked"),
            LicenseError::InvalidFormat => (StatusCode::BAD_REQUEST, "Invalid license format"),
            LicenseError::InvalidSignature => (StatusCode::BAD_REQUEST, "Invalid signature"),
            LicenseError::QuotaExceeded => (StatusCode::TOO_MANY_REQUESTS, "Quota exceeded"),
            LicenseError::AgentLimitExceeded => (StatusCode::TOO_MANY_REQUESTS, "Agent limit exceeded"),
            LicenseError::VerificationFailed(msg) => (StatusCode::BAD_REQUEST, &msg),
            LicenseError::DatabaseError(msg) => (StatusCode::INTERNAL_SERVER_ERROR, &msg),
            LicenseError::StripeError(msg) => (StatusCode::INTERNAL_SERVER_ERROR, &msg),
            LicenseError::NotFound => (StatusCode::NOT_FOUND, "License not found"),
        };

        (
            status,
            Json(ErrorResponse {
                error: error_msg.to_string(),
                status_code: status.as_u16(),
            }),
        )
            .into_response()
    }
}

#[cfg(feature = "axum")]
pub async fn checkout_handler(
    Json(_payload): Json<CheckoutRequest>,
) -> Result<Json<CheckoutResponse>, LicenseError> {
    Err(LicenseError::StripeError("Not implemented".into()))
}

#[cfg(feature = "axum")]
pub async fn verify_handler(
    Path(_key): Path<String>,
    Json(_payload): Json<VerifyRequest>,
) -> Result<Json<VerifyResponse>, LicenseError> {
    Err(LicenseError::NotFound)
}

#[cfg(feature = "axum")]
pub async fn usage_handler(
    Json(_payload): Json<UsageRequest>,
) -> Result<Json<UsageResponse>, LicenseError> {
    Err(LicenseError::NotFound)
}

#[cfg(feature = "axum")]
pub async fn renew_handler(
    Path(_key): Path<String>,
) -> Result<Json<serde_json::Value>, LicenseError> {
    Err(LicenseError::NotFound)
}

#[cfg(feature = "axum")]
pub async fn cancel_handler(
    Json(_payload): Json<serde_json::Value>,
) -> Result<Json<serde_json::Value>, LicenseError> {
    Err(LicenseError::NotFound)
}

#[cfg(feature = "axum")]
pub async fn invoices_handler(
    Path(_customer_id): Path<String>,
) -> Result<Json<Vec<Invoice>>, LicenseError> {
    Ok(Json(vec![]))
}

#[cfg(feature = "axum")]
pub async fn stripe_webhook_handler(
    Json(_payload): Json<WebhookPayload>,
) -> Result<StatusCode, LicenseError> {
    Ok(StatusCode::OK)
}

#[cfg(feature = "axum")]
pub async fn generate_handler(
    Json(_payload): Json<GenerateRequest>,
) -> Result<Json<GenerateResponse>, LicenseError> {
    Err(LicenseError::VerificationFailed("Admin only".into()))
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_handler_types_compile() {
        // Just ensure types compile
    }
}
