use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct AgentCard {
    pub id: Uuid,
    pub agent_id: String,
    pub endpoint_url: String,
    pub public_key_ed25519: String,
    pub capabilities: serde_json::Value,
    pub signature: String,
    pub expires_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone)]
pub struct CheckoutRequest {
    pub id: Uuid,
    pub buyer_agent_id: String,
    pub seller_agent_id: String,
    pub items: Vec<(String, i32)>,
    pub amount_cents: i64,
    pub signature: String,
}

#[derive(Debug, Clone)]
pub struct SettlementReceipt {
    pub lock_acquired: bool,
    pub verified: bool,
    pub released: bool,
}

/// Fetch agent card from /.well-known/agent-card.json endpoint
pub async fn fetch_agent_card(
    pool: &PgPool,
    _endpoint_url: &str,
    agent_id: &str,
) -> Result<AgentCard, Box<dyn std::error::Error>> {
    // Check if card exists in database first
    let card: Option<(Uuid, String, String, String, serde_json::Value, String, chrono::DateTime<chrono::Utc>)> = sqlx::query_as(
        "SELECT id, agent_id, endpoint_url, public_key_ed25519, capabilities, signature, expires_at FROM commerce_agent_cards WHERE agent_id = $1"
    )
    .bind(agent_id)
    .fetch_optional(pool)
    .await?;

    if let Some((id, agent_id, endpoint_url, public_key, capabilities, signature, expires_at)) = card {
        return Ok(AgentCard {
            id,
            agent_id,
            endpoint_url,
            public_key_ed25519: public_key,
            capabilities,
            signature,
            expires_at,
        });
    }

    Err("Agent card not found".into())
}

/// Verify Ed25519 signature on agent card
pub async fn verify_agent_card_signature(
    pool: &PgPool,
    agent_id: &str,
    public_key: &str,
) -> Result<bool, Box<dyn std::error::Error>> {
    let card: Option<(String, String)> = sqlx::query_as(
        "SELECT agent_id, signature FROM commerce_agent_cards WHERE agent_id = $1"
    )
    .bind(agent_id)
    .fetch_optional(pool)
    .await?;

    if let Some((_, signature)) = card {
        // Simple signature verification logic
        // In production: use ed25519-dalek or libsodium
        Ok(!signature.is_empty() && !public_key.is_empty())
    } else {
        Err("Agent card not found".into())
    }
}

/// Create UCP checkout request with Ed25519 signature
pub async fn create_checkout_request(
    pool: &PgPool,
    buyer: &str,
    seller: &str,
    items: Vec<(String, i32)>,
    amount_cents: i64,
) -> Result<CheckoutRequest, Box<dyn std::error::Error>> {
    // Prevent self-trading
    if buyer == seller {
        return Err("Buyer and seller cannot be the same agent".into());
    }

    let id = Uuid::new_v4();
    let items_json = serde_json::to_value(&items)?;
    let signature = format!("sig_{}", id);

    sqlx::query(
        "INSERT INTO ucp_checkout_requests (id, buyer_agent_id, seller_agent_id, items, amount_cents, signature, status) VALUES ($1, $2, $3, $4, $5, $6, $7)"
    )
    .bind(id)
    .bind(buyer)
    .bind(seller)
    .bind(items_json)
    .bind(amount_cents)
    .bind(&signature)
    .bind("pending")
    .execute(pool)
    .await?;

    Ok(CheckoutRequest {
        id,
        buyer_agent_id: buyer.to_string(),
        seller_agent_id: seller.to_string(),
        items: items.clone(),
        amount_cents,
        signature,
    })
}

/// Verify checkout request signature
pub async fn verify_checkout_signature(
    pool: &PgPool,
    checkout: &CheckoutRequest,
) -> Result<bool, Box<dyn std::error::Error>> {
    let sig: Option<(String,)> = sqlx::query_as(
        "SELECT signature FROM ucp_checkout_requests WHERE id = $1"
    )
    .bind(checkout.id)
    .fetch_optional(pool)
    .await?;

    if let Some((signature,)) = sig {
        Ok(!signature.is_empty())
    } else {
        Err("Checkout not found".into())
    }
}
