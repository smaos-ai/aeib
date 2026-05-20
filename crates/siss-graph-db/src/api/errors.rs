use axum::{
    Json,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use serde::Serialize;

/// API error response
#[derive(Debug, Serialize)]
pub struct ApiErrorResponse {
    pub error: String,
    pub code: String,
}

/// API error type
#[derive(Debug)]
pub enum ApiError {
    InvalidParameter(String),
    NotFound(String),
    InternalError(String),
    DatabaseError(String),
}

/// API result type
pub type ApiResult<T> = Result<T, ApiError>;

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, code, message) = match self {
            ApiError::InvalidParameter(msg) => (StatusCode::BAD_REQUEST, "INVALID_PARAMETER", msg),
            ApiError::NotFound(msg) => (StatusCode::NOT_FOUND, "NOT_FOUND", msg),
            ApiError::InternalError(msg) => {
                (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", msg)
            }
            ApiError::DatabaseError(msg) => {
                (StatusCode::INTERNAL_SERVER_ERROR, "DATABASE_ERROR", msg)
            }
        };

        let response = ApiErrorResponse {
            error: message,
            code: code.to_string(),
        };

        (status, Json(response)).into_response()
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(err: sqlx::Error) -> Self {
        ApiError::DatabaseError(err.to_string())
    }
}
