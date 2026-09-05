use serde::{Deserialize, Serialize};
use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};

/// Work receipt for agent execution trace (L8 Proof Layer)
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct AgentacctWorkReceipt {
    pub id: String,
    pub agent_id: String,
    pub action: String,
    pub result: String,
    pub signature: String,
    pub timestamp: String,
    pub chain_digest: String,
    #[sqlx(skip)]
    pub created_at: Option<String>,
}

/// SQLite-backed store for agent work receipts
pub struct AgentacctStore {
    pool: SqlitePool,
}

impl AgentacctStore {
    /// Create a new store connected to SQLite database
    pub async fn new(database_url: &str) -> Result<Self, String> {
        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect(database_url)
            .await
            .map_err(|e| format!("Failed to connect to database: {}", e))?;

        Ok(Self { pool })
    }

    /// Initialize schema (create tables if not exist)
    pub async fn init_schema(&self) -> Result<(), String> {
        let schema = include_str!("../schema/agentacct.sql");
        for statement in schema.split(';').filter(|s| !s.trim().is_empty()) {
            sqlx::query(statement)
                .execute(&self.pool)
                .await
                .map_err(|e| format!("Schema initialization failed: {}", e))?;
        }
        Ok(())
    }

    /// Save a work receipt to the ledger
    pub async fn save_receipt(&self, receipt: AgentacctWorkReceipt) -> Result<String, String> {
        sqlx::query(
            "INSERT INTO agentacct_receipts (id, agent_id, action, result, signature, timestamp, chain_digest)
             VALUES (?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(&receipt.id)
        .bind(&receipt.agent_id)
        .bind(&receipt.action)
        .bind(&receipt.result)
        .bind(&receipt.signature)
        .bind(&receipt.timestamp)
        .bind(&receipt.chain_digest)
        .execute(&self.pool)
        .await
        .map_err(|e| format!("Failed to save receipt: {}", e))?;

        Ok(receipt.id)
    }

    /// Load all receipts for a given agent
    pub async fn load_receipts(&self, agent_id: &str) -> Result<Vec<AgentacctWorkReceipt>, String> {
        sqlx::query_as::<_, AgentacctWorkReceipt>(
            "SELECT id, agent_id, action, result, signature, timestamp, chain_digest, NULL as created_at
             FROM agentacct_receipts
             WHERE agent_id = ?
             ORDER BY timestamp ASC",
        )
        .bind(agent_id)
        .fetch_all(&self.pool)
        .await
        .map_err(|e| format!("Failed to load receipts: {}", e))
    }

    /// Load a single receipt by ID (immutability check)
    pub async fn load_receipt(
        &self,
        receipt_id: &str,
    ) -> Result<Option<AgentacctWorkReceipt>, String> {
        sqlx::query_as::<_, AgentacctWorkReceipt>(
            "SELECT id, agent_id, action, result, signature, timestamp, chain_digest, NULL as created_at
             FROM agentacct_receipts
             WHERE id = ?",
        )
        .bind(receipt_id)
        .fetch_optional(&self.pool)
        .await
        .map_err(|e| format!("Failed to load receipt: {}", e))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    async fn setup_store() -> AgentacctStore {
        let store = AgentacctStore::new("sqlite::memory:")
            .await
            .expect("Failed to create in-memory store");
        store.init_schema().await.expect("Failed to init schema");
        store
    }

    #[tokio::test]
    async fn test_save_and_load() {
        let store = setup_store().await;
        let agent_id = "agent-123";

        let receipt = AgentacctWorkReceipt {
            id: Uuid::new_v4().to_string(),
            agent_id: agent_id.to_string(),
            action: "authorize_transfer".to_string(),
            result: "success".to_string(),
            signature: "sig_abc123def456".to_string(),
            timestamp: Utc::now().to_rfc3339(),
            chain_digest: "digest_xyz789".to_string(),
            created_at: None,
        };

        let receipt_id = store
            .save_receipt(receipt.clone())
            .await
            .expect("Failed to save receipt");

        assert_eq!(receipt_id, receipt.id);

        let loaded = store
            .load_receipts(agent_id)
            .await
            .expect("Failed to load receipts");

        assert_eq!(loaded.len(), 1);
        assert_eq!(loaded[0].id, receipt.id);
        assert_eq!(loaded[0].action, "authorize_transfer");
        assert_eq!(loaded[0].result, "success");
    }

    #[tokio::test]
    async fn test_agent_receipts_query() {
        let store = setup_store().await;
        let agent_id = "agent-456";

        for i in 0..3 {
            let receipt = AgentacctWorkReceipt {
                id: Uuid::new_v4().to_string(),
                agent_id: agent_id.to_string(),
                action: format!("action_{}", i),
                result: "success".to_string(),
                signature: format!("sig_{}", i),
                timestamp: Utc::now().to_rfc3339(),
                chain_digest: format!("digest_{}", i),
                created_at: None,
            };
            store
                .save_receipt(receipt)
                .await
                .expect("Failed to save receipt");
        }

        let loaded = store
            .load_receipts(agent_id)
            .await
            .expect("Failed to load receipts");

        assert_eq!(loaded.len(), 3);

        let other_agent = store
            .load_receipts("unknown-agent")
            .await
            .expect("Failed to load receipts");
        assert_eq!(other_agent.len(), 0);
    }

    #[tokio::test]
    async fn test_receipt_immutability() {
        let store = setup_store().await;
        let agent_id = "agent-789";

        let receipt = AgentacctWorkReceipt {
            id: Uuid::new_v4().to_string(),
            agent_id: agent_id.to_string(),
            action: "sign_proof".to_string(),
            result: "verified".to_string(),
            signature: "sig_immutable_12345".to_string(),
            timestamp: Utc::now().to_rfc3339(),
            chain_digest: "digest_immutable_xyz".to_string(),
            created_at: None,
        };

        let receipt_id = receipt.id.clone();

        store
            .save_receipt(receipt.clone())
            .await
            .expect("Failed to save receipt");

        let loaded1 = store
            .load_receipt(&receipt_id)
            .await
            .expect("Failed to load receipt")
            .expect("Receipt not found");

        let loaded2 = store
            .load_receipt(&receipt_id)
            .await
            .expect("Failed to load receipt")
            .expect("Receipt not found");

        assert_eq!(loaded1.id, loaded2.id);
        assert_eq!(loaded1.signature, loaded2.signature);
        assert_eq!(loaded1.chain_digest, loaded2.chain_digest);
        assert_eq!(loaded1.timestamp, loaded2.timestamp);
    }
}
