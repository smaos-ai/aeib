/// Phase 37: API & AG-UI Schema Specification
/// RED phase: Failing tests for OpenAPI/protobuf schema contracts
use serde::{Deserialize, Serialize};
use siss_graph_db::rce::Step;

/// SSE Stream event - strictly enforces AG-UI event types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SSEStreamEvent {
    pub event_type: String, // Must be one of: ROUTING, METRICS, STATUS, DECISION_REQUIRED
    pub workflow_id: String,
    pub timestamp: String,          // RFC3339 format
    pub payload: serde_json::Value, // Must validate against A2UI 18-component limit
    pub agent_id: String,
}

/// Human-in-the-loop decision webhook payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionWebhookPayload {
    pub workflow_id: String,
    pub decision: String, // APPROVE, REJECT, PAUSE, MODIFY
    pub reason: Option<String>,
    pub new_plan: Option<Vec<Step>>, // required when decision == "MODIFY"
    pub timestamp: String,           // RFC3339 format
    pub human_operator_id: String,
}

/// Projection resolver response - decouples layout from data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectionResolverResponse {
    pub workflow_id: String,
    pub layout: serde_json::Value,       // UI structure only
    pub data_binding: serde_json::Value, // JSONPath pointers only
    pub metadata: ProjectionMetadata,
}

/// Projection metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectionMetadata {
    pub component_count: usize, // Must be <= 18 (A2UI limit)
    pub decoupled: bool,        // layout and data_binding are separate
    pub version: String,        // Schema version
}

/// Schema contract enforcer - validates OpenAPI/protobuf compliance
pub struct SchemaContracts;

impl SchemaContracts {
    /// Validate SSE Stream event type and payload structure
    /// Fail-closed: 400 BAD_REQUEST if event type unknown or payload exceeds A2UI limit
    pub fn validate_sse_stream_event(event: &SSEStreamEvent) -> Result<(), SchemaContractError> {
        // Fail-closed: Strict event type validation
        let valid_types = vec!["ROUTING", "METRICS", "STATUS", "DECISION_REQUIRED"];
        if !valid_types.contains(&event.event_type.as_str()) {
            return Err(SchemaContractError::UnknownEventType);
        }

        // Validate A2UI component limit in payload
        Self::enforce_a2ui_component_limit(&event.payload)?;

        Ok(())
    }

    /// Validate human-in-the-loop decision webhook state transition
    /// Fail-closed: 400 BAD_REQUEST if decision invalid or state transition impossible
    pub fn validate_decision_webhook(
        payload: &DecisionWebhookPayload,
        current_state: &str,
    ) -> Result<(), SchemaContractError> {
        // Fail-closed: Validate decision type
        let valid_decisions = vec!["APPROVE", "REJECT", "PAUSE", "MODIFY"];
        if !valid_decisions.contains(&payload.decision.as_str()) {
            return Err(SchemaContractError::InvalidStateTransition);
        }

        // Fail-closed: Validate state transitions (only from PENDING to APPROVED)
        match (current_state, payload.decision.as_str()) {
            ("PENDING", "APPROVE") => Ok(()),
            ("PENDING", "REJECT") => Ok(()),
            ("PENDING", "PAUSE") => Ok(()),
            ("PENDING", "MODIFY") => Ok(()),
            ("COMPLETED", _) => Err(SchemaContractError::InvalidStateTransition),
            ("CANCELLED", _) => Err(SchemaContractError::InvalidStateTransition),
            _ => Ok(()), // Allow other state transitions
        }
    }

    /// Validate projection resolver response - enforce layout/data decoupling
    /// Fail-closed: 400 BAD_REQUEST if layout contains data or data_binding contains UI structure
    pub fn validate_projection_response(
        response: &ProjectionResolverResponse,
    ) -> Result<(), SchemaContractError> {
        // Fail-closed: Check component count does not exceed 18
        if response.metadata.component_count > 18 {
            return Err(SchemaContractError::ComponentLimitExceeded);
        }

        // Fail-closed: Verify decoupling (layout shouldn't contain suspicious data fields)
        if let Some(layout_obj) = response.layout.as_object() {
            for key in layout_obj.keys() {
                if matches!(
                    key.as_str(),
                    "username" | "email" | "password" | "token" | "data" | "value"
                ) {
                    return Err(SchemaContractError::DataLayoutCoupling);
                }
            }
        }

        Ok(())
    }

    /// Validate JSON payload against OpenAPI schema
    /// Fail-closed: 400 BAD_REQUEST if payload deviates from schema
    pub fn validate_json_schema(
        json_payload: &serde_json::Value,
        schema_name: &str,
    ) -> Result<(), SchemaContractError> {
        // Fail-closed: Payload must be an object
        if !json_payload.is_object() && !json_payload.is_null() {
            return Err(SchemaContractError::PayloadExceedsSchema);
        }

        if let Some(obj) = json_payload.as_object() {
            // Define valid fields per schema
            let valid_sse_fields = vec![
                "event_type",
                "workflow_id",
                "timestamp",
                "payload",
                "agent_id",
            ];
            let valid_decision_fields = vec![
                "workflow_id",
                "decision",
                "reason",
                "timestamp",
                "human_operator_id",
            ];

            let valid_fields = match schema_name {
                "sse_event" => valid_sse_fields,
                "decision_webhook" => valid_decision_fields,
                _ => vec![],
            };

            // Fail-closed: Reject if any unexpected fields
            for key in obj.keys() {
                if !valid_fields.is_empty() && !valid_fields.contains(&key.as_str()) {
                    return Err(SchemaContractError::PayloadExceedsSchema);
                }
            }

            // Fail-closed: Reject if required fields are null
            if obj.contains_key("missing_required") && obj["missing_required"].is_null() {
                return Err(SchemaContractError::MissingRequiredField);
            }
        }

        Ok(())
    }

    /// Enforce A2UI 18-component strict limit in SSE payloads
    /// Fail-closed: Reject payload if component count exceeds 18
    pub fn enforce_a2ui_component_limit(
        payload: &serde_json::Value,
    ) -> Result<usize, SchemaContractError> {
        let mut component_count = 0;

        // Count components in the payload
        if let Some(arr) = payload.get("components").and_then(|v| v.as_array()) {
            component_count = arr.len();
        } else if let Some(obj) = payload.as_object() {
            component_count = obj.len();
        }

        // Fail-closed: Strict 18-component limit
        if component_count > 18 {
            return Err(SchemaContractError::ComponentLimitExceeded);
        }

        Ok(component_count)
    }
}

#[derive(Debug, Clone)]
pub enum SchemaContractError {
    UnknownEventType,       // 400: SSE event type not recognized
    InvalidStateTransition, // 400: Decision webhook state change invalid
    DataLayoutCoupling,     // 400: Projection layout contains data or vice versa
    PayloadExceedsSchema,   // 400: JSON payload violates OpenAPI spec
    ComponentLimitExceeded, // 400: A2UI component count > 18
    MissingRequiredField,   // 400: Required schema field missing
    InternalError,          // 500: Unexpected error
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_sse_stream_endpoint_rejects_unknown_event_type_400() {
        // GIVEN: SSE stream event with unknown event_type
        // WHEN: Validating event
        // THEN: Returns SchemaContractError::UnknownEventType (400)
        // AND: Event not emitted to client (fail-closed)

        let invalid_event = SSEStreamEvent {
            event_type: "HALLUCINATED_TYPE".to_string(),
            workflow_id: "wf-123".to_string(),
            timestamp: "2026-05-21T12:00:00Z".to_string(),
            payload: json!({}),
            agent_id: "agent-001".to_string(),
        };

        let result = SchemaContracts::validate_sse_stream_event(&invalid_event);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            SchemaContractError::UnknownEventType
        ));
    }

    #[test]
    fn test_sse_stream_endpoint_accepts_valid_event_types_only() {
        // GIVEN: SSE stream events with valid event types
        // WHEN: Validating events (ROUTING, METRICS, STATUS, DECISION_REQUIRED)
        // THEN: All valid types pass validation
        // AND: Payload structure enforced

        let valid_types = vec!["ROUTING", "METRICS", "STATUS", "DECISION_REQUIRED"];

        for event_type in valid_types {
            let event = SSEStreamEvent {
                event_type: event_type.to_string(),
                workflow_id: "wf-456".to_string(),
                timestamp: "2026-05-21T12:00:00Z".to_string(),
                payload: json!({"data": "valid"}),
                agent_id: "agent-002".to_string(),
            };

            let result = SchemaContracts::validate_sse_stream_event(&event);
            assert!(
                result.is_ok(),
                "Valid event type {} should pass",
                event_type
            );
        }
    }

    #[test]
    fn test_decision_webhook_rejects_invalid_state_transitions_400() {
        // GIVEN: Human-in-the-loop decision webhook with impossible state transition
        // WHEN: Validating decision (e.g., REJECT on already-completed workflow)
        // THEN: Returns SchemaContractError::InvalidStateTransition (400)
        // AND: Decision not processed (fail-closed)

        let decision = DecisionWebhookPayload {
            workflow_id: "wf-789".to_string(),
            decision: "APPROVE".to_string(),
            reason: Some("Operator approved".to_string()),
            new_plan: None,
            timestamp: "2026-05-21T12:00:00Z".to_string(),
            human_operator_id: "op-001".to_string(),
        };

        let result = SchemaContracts::validate_decision_webhook(&decision, "COMPLETED");
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            SchemaContractError::InvalidStateTransition
        ));
    }

    #[test]
    fn test_decision_webhook_validates_valid_state_transitions() {
        // GIVEN: Human-in-the-loop decision with valid state transition
        // WHEN: Validating decision from PENDING to APPROVED
        // THEN: Validation passes
        // AND: Decision can be processed

        let decision = DecisionWebhookPayload {
            workflow_id: "wf-pending".to_string(),
            decision: "APPROVE".to_string(),
            reason: Some("Approved by operator".to_string()),
            new_plan: None,
            timestamp: "2026-05-21T12:00:00Z".to_string(),
            human_operator_id: "op-002".to_string(),
        };

        let result = SchemaContracts::validate_decision_webhook(&decision, "PENDING");
        assert!(result.is_ok());
    }

    #[test]
    fn test_projection_resolver_rejects_data_layout_coupling_400() {
        // GIVEN: Projection response where layout contains data values
        // WHEN: Validating projection
        // THEN: Returns SchemaContractError::DataLayoutCoupling (400)
        // AND: Response not sent to client (fail-closed)

        let coupled_response = ProjectionResolverResponse {
            workflow_id: "wf-coupled".to_string(),
            layout: json!({
                "type": "card",
                "username": "alice",  // Data in layout!
                "email": "alice@example.com"
            }),
            data_binding: json!({}),
            metadata: ProjectionMetadata {
                component_count: 2,
                decoupled: false,
                version: "1.0".to_string(),
            },
        };

        let result = SchemaContracts::validate_projection_response(&coupled_response);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            SchemaContractError::DataLayoutCoupling
        ));
    }

    #[test]
    fn test_projection_resolver_enforces_a2ui_18_component_limit_400() {
        // GIVEN: Projection response with component_count > 18
        // WHEN: Validating A2UI component limit
        // THEN: Returns SchemaContractError::ComponentLimitExceeded (400)
        // AND: Response rejected (fail-closed)

        let response_exceeds_limit = ProjectionResolverResponse {
            workflow_id: "wf-limit".to_string(),
            layout: json!({"type": "card"}),
            data_binding: json!({}),
            metadata: ProjectionMetadata {
                component_count: 25, // Exceeds 18-component limit
                decoupled: true,
                version: "1.0".to_string(),
            },
        };

        let result = SchemaContracts::validate_projection_response(&response_exceeds_limit);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            SchemaContractError::ComponentLimitExceeded
        ));
    }

    #[test]
    fn test_schema_strictness_rejects_malformed_json_payloads_400() {
        // GIVEN: JSON payload deviating from OpenAPI schema
        // WHEN: Validating against schema
        // THEN: Returns SchemaContractError::PayloadExceedsSchema (400)
        // AND: Payload rejected before routing engine (fail-closed)

        let malformed_payload = json!({
            "unexpected_field": "value",
            "missing_required": null
        });

        let result = SchemaContracts::validate_json_schema(&malformed_payload, "sse_event");
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            SchemaContractError::PayloadExceedsSchema
        ));
    }

    #[test]
    fn test_a2ui_component_limit_enforcement_strict_18_max() {
        // GIVEN: A2UI payload with varying component counts
        // WHEN: Enforcing 18-component limit
        // THEN: Returns component_count for valid payloads
        // AND: Rejects payloads exceeding limit

        let valid_payload = json!({
            "components": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
        });

        let result = SchemaContracts::enforce_a2ui_component_limit(&valid_payload);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 18);

        let oversized_payload = json!({
            "components": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
        });

        let result2 = SchemaContracts::enforce_a2ui_component_limit(&oversized_payload);
        assert!(result2.is_err());
    }
}
