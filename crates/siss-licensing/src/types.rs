use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Sku {
    Starter,
    Pro,
    Enterprise,
}

impl Sku {
    pub fn agent_limit(&self) -> Option<u32> {
        match self {
            Self::Starter => Some(5),
            Self::Pro => Some(50),
            Self::Enterprise => None,
        }
    }

    pub fn daily_api_limit(&self) -> Option<u64> {
        match self {
            Self::Starter => Some(1_000),
            Self::Pro => Some(100_000),
            Self::Enterprise => None,
        }
    }

    pub fn monthly_price_cents(&self) -> Option<i64> {
        match self {
            Self::Starter => Some(2999),
            Self::Pro => Some(9999),
            Self::Enterprise => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Starter => "Starter",
            Self::Pro => "Pro",
            Self::Enterprise => "Enterprise",
        }
    }

    #[allow(clippy::should_implement_trait)]
    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "Starter" => Some(Self::Starter),
            "Pro" => Some(Self::Pro),
            "Enterprise" => Some(Self::Enterprise),
            _ => None,
        }
    }

    pub fn to_byte(&self) -> u8 {
        match self {
            Self::Starter => 0u8,
            Self::Pro => 1u8,
            Self::Enterprise => 2u8,
        }
    }

    pub fn from_byte(b: u8) -> Option<Self> {
        match b {
            0 => Some(Self::Starter),
            1 => Some(Self::Pro),
            2 => Some(Self::Enterprise),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct License {
    pub id: Uuid,
    pub key: String,
    pub customer_id: Uuid,
    pub sku: Sku,
    pub expires_at: DateTime<Utc>,
    pub revoked: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct VerifiedLicense {
    pub sku: Sku,
    pub limits: LicenseLimits,
    pub expiry_at: DateTime<Utc>,
    pub customer_id: Uuid,
}

#[derive(Debug, Clone, Copy)]
pub struct LicenseLimits {
    pub agent_limit: Option<u32>,
    pub api_quota_daily: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Invoice {
    pub id: Uuid,
    pub customer_id: Uuid,
    pub amount_cents: i64,
    pub sku: Sku,
    pub status: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckoutSession {
    pub session_id: String,
    pub url: String,
    pub customer_id: Uuid,
    pub amount_cents: i64,
    pub sku: Sku,
}

#[derive(Debug, Clone)]
pub enum LicenseEvent {
    Generated {
        customer_id: Uuid,
        sku: Sku,
    },
    Validated {
        key: String,
        result: bool,
    },
    UsageRecorded {
        key: String,
        calls: u64,
    },
    Renewed {
        key: String,
    },
    Revoked {
        customer_id: Uuid,
    },
    PaymentReceived {
        customer_id: Uuid,
        amount_cents: i64,
    },
}

#[derive(Debug, Clone)]
pub enum LicenseError {
    Expired,
    Revoked,
    InvalidFormat,
    InvalidSignature,
    QuotaExceeded,
    AgentLimitExceeded,
    VerificationFailed(String),
    DatabaseError(String),
    StripeError(String),
    NotFound,
}

impl std::fmt::Display for LicenseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Expired => write!(f, "License expired"),
            Self::Revoked => write!(f, "License revoked"),
            Self::InvalidFormat => write!(f, "Invalid license format"),
            Self::InvalidSignature => write!(f, "Invalid license signature"),
            Self::QuotaExceeded => write!(f, "API quota exceeded"),
            Self::AgentLimitExceeded => write!(f, "Agent limit exceeded"),
            Self::VerificationFailed(msg) => write!(f, "Verification failed: {}", msg),
            Self::DatabaseError(msg) => write!(f, "Database error: {}", msg),
            Self::StripeError(msg) => write!(f, "Stripe error: {}", msg),
            Self::NotFound => write!(f, "License not found"),
        }
    }
}

impl std::error::Error for LicenseError {}
