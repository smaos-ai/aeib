/// Verification Gate: post-execution output validation for SLM responses.
/// Detects malformed JSON and triggers cloud fallback on failure.

use thiserror::Error;

/// Verified output passed through the gate.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedOutput {
    pub raw: String,
}

/// Error type for verification failures.
#[derive(Debug, Error, PartialEq, Eq)]
#[error("malformed output: not valid JSON object/array")]
pub struct GateError {
    pub raw: String,
}

/// Verification Gate: validates SLM output structure.
pub struct VerificationGate;

impl VerificationGate {
    /// Check if output is valid JSON (object or array root).
    /// Invariant 3: Valid JSON → Ok. Invalid → Err with original output for fallback re-route.
    pub fn check(output: &str) -> Result<VerifiedOutput, GateError> {
        // Try to parse as JSON
        match serde_json::from_str::<serde_json::Value>(output) {
            Ok(value) => {
                // Accept JSON objects and arrays; reject scalars
                match value {
                    serde_json::Value::Object(_) | serde_json::Value::Array(_) => {
                        Ok(VerifiedOutput {
                            raw: output.to_string(),
                        })
                    }
                    _ => Err(GateError {
                        raw: output.to_string(),
                    }),
                }
            }
            Err(_) => Err(GateError {
                raw: output.to_string(),
            }),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_json_object() {
        let output = r#"{"tool":"bash","args":["ls"]}"#;
        let result = VerificationGate::check(output);
        assert!(result.is_ok());
    }

    #[test]
    fn test_valid_json_array() {
        let output = r#"[1,2,3]"#;
        let result = VerificationGate::check(output);
        assert!(result.is_ok());
    }

    #[test]
    fn test_invalid_json_string() {
        let output = "this is not json";
        let result = VerificationGate::check(output);
        assert!(result.is_err());
    }

    #[test]
    fn test_json_scalar_rejected() {
        let output = r#""just a string""#;
        let result = VerificationGate::check(output);
        assert!(result.is_err(), "JSON scalar must be rejected");
    }
}
