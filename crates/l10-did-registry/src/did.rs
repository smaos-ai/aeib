use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct DID {
    pub method: String,      // "did:sov", "did:key", "did:web"
    pub identifier: String,  // unique part
}

impl DID {
    pub fn new(method: String, identifier: String) -> Self {
        Self {
            method,
            identifier,
        }
    }

    pub fn sov(identifier: String) -> Self {
        Self {
            method: "did:sov".to_string(),
            identifier,
        }
    }

    pub fn key(public_key_hash: String) -> Self {
        Self {
            method: "did:key".to_string(),
            identifier: public_key_hash,
        }
    }

    pub fn web(domain_hash: String) -> Self {
        Self {
            method: "did:web".to_string(),
            identifier: domain_hash,
        }
    }

    pub fn to_string(&self) -> String {
        format!("{}:{}", self.method, self.identifier)
    }

    pub fn from_string(did_str: &str) -> Result<Self, String> {
        let parts: Vec<&str> = did_str.split(':').collect();
        if parts.len() < 3 {
            return Err("Invalid DID format".to_string());
        }
        let method = format!("{}:{}", parts[0], parts[1]);
        let identifier = parts[2..].join(":");
        Ok(DID::new(method, identifier))
    }
}

impl fmt::Display for DID {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}:{}", self.method, self.identifier)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DidDocument {
    pub id: DID,
    pub controller: Option<String>,
    pub public_keys: Vec<PublicKey>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
    pub proof: Option<String>,
}

impl DidDocument {
    pub fn new(id: DID, controller: Option<String>) -> Self {
        let now = chrono::Utc::now();
        Self {
            id,
            controller,
            public_keys: Vec::new(),
            created_at: now,
            updated_at: now,
            proof: None,
        }
    }

    pub fn add_public_key(&mut self, key: PublicKey) {
        self.public_keys.push(key);
        self.updated_at = chrono::Utc::now();
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublicKey {
    pub id: String,
    pub key_type: String, // "Ed25519VerificationKey2020"
    pub public_key_hex: String,
}

impl PublicKey {
    pub fn new(id: String, key_type: String, public_key_hex: String) -> Self {
        Self {
            id,
            key_type,
            public_key_hex,
        }
    }
}
