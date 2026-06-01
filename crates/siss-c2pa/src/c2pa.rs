use serde_json::{json, Value};

/// SMAOS ResearchResult structure (from siss-gatekeeper/src/pipeline/research.rs)
#[derive(Debug, Clone)]
pub struct ResearchResult {
    pub query: String,
    pub answer: String,
    pub source: String,        // "local_cache", "perplexity_mcp", etc.
    pub timestamp: String,
    pub merkle_hash: String,
}

/// Convert SMAOS ResearchResult capsule to C2PA manifest JSON.
///
/// Creates a C2PA-compatible manifest structure with SMAOS research result assertion.
/// The manifest follows C2PA specification with custom "smaos:research_result" assertion.
///
/// Example output:
/// {
///   "claims": [
///     {
///       "kind": "c2pa.assertion.user_defined",
///       "data": {
///         "query": "...",
///         "answer": "...",
///         "source": "...",
///         "timestamp": "...",
///         "merkle_hash": "..."
///       }
///     }
///   ]
/// }
pub fn capsule_to_c2pa_manifest(
    capsule: &ResearchResult,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    // Create C2PA-compatible manifest structure
    // This follows C2PA spec with custom assertion embedded
    let manifest = json!({
        "claims": [
            {
                "kind": "c2pa.assertion.user_defined",
                "label": "smaos:research_result",
                "data": {
                    "query": capsule.query,
                    "answer": capsule.answer,
                    "source": capsule.source,
                    "timestamp": capsule.timestamp,
                    "merkle_hash": capsule.merkle_hash,
                }
            }
        ],
        "provider": "smaos-research-gateway",
        "spec_version": "1.0"
    });

    // Serialize to JSON bytes
    Ok(serde_json::to_vec(&manifest)?)
}

/// Convert incoming C2PA manifest bytes to SMAOS ResearchResult.
///
/// Deserializes C2PA manifest JSON and extracts the smaos:research_result assertion.
pub fn c2pa_manifest_to_capsule(
    manifest_bytes: &[u8],
) -> Result<ResearchResult, Box<dyn std::error::Error>> {
    // Parse manifest JSON
    let manifest_json: Value = serde_json::from_slice(manifest_bytes)?;

    // Extract claims (C2PA manifest structure)
    let claims = manifest_json
        .get("claims")
        .and_then(|c| c.as_array())
        .ok_or("No claims found in manifest")?;

    if claims.is_empty() {
        return Err("Manifest has no claims".into());
    }

    let claim = &claims[0];

    // Extract the custom assertion data
    let data = claim
        .get("data")
        .ok_or("No data field in claim")?;

    // Map JSON to ResearchResult
    let result = ResearchResult {
        query: data
            .get("query")
            .and_then(|q| q.as_str())
            .ok_or("query not found")?
            .to_string(),
        answer: data
            .get("answer")
            .and_then(|a| a.as_str())
            .ok_or("answer not found")?
            .to_string(),
        source: data
            .get("source")
            .and_then(|s| s.as_str())
            .ok_or("source not found")?
            .to_string(),
        timestamp: data
            .get("timestamp")
            .and_then(|t| t.as_str())
            .ok_or("timestamp not found")?
            .to_string(),
        merkle_hash: data
            .get("merkle_hash")
            .and_then(|h| h.as_str())
            .ok_or("merkle_hash not found")?
            .to_string(),
    };

    Ok(result)
}
