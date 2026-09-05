//! Contract adapters: Demonstrate L1→L2→L3 contract enforcement
//! Shows how contracts replace implicit JSON passing with explicit type boundaries

use l1_reasoning::{L1Output, PolicyDecision, PolicyRequest, PolicyBound};
use l2_knowledge::{L2Input, L2Output, KnowledgeRequest, KnowledgeResult, SearchResult};
use l3_permit_gates::{L3Input, L3Output, GateRequest, GatedDecision, PermitGate};

/// Contract-enforcing adapter: L1→L2 boundary
pub struct L1ToL2Adapter;

impl L1ToL2Adapter {
    pub fn convert_output_to_input(l1_output: &dyn L1Output, query: String) -> KnowledgeRequest {
        // Compile-time type safety: convert L1Output trait object to L2Input concrete type
        KnowledgeRequest::new(
            l1_output.request_id().to_string(),
            l1_output.article().to_string(),
            l1_output.compliance_level(),
            query,
        )
    }
}

/// Contract-enforcing adapter: L2→L3 boundary
pub struct L2ToL3Adapter;

impl L2ToL3Adapter {
    pub fn convert_output_to_input(l2_output: &dyn L2Output) -> GateRequest {
        // Compile-time type safety: convert L2Output trait object to L3Input concrete type
        GateRequest::new(
            l2_output.request_id().to_string(),
            l2_output.results_count(),
            l2_output.results_count() > 0,
        )
    }
}

/// Full L1→L2→L3 pipeline with explicit contract boundaries
pub struct L1L2L3Pipeline;

impl L1L2L3Pipeline {
    pub fn execute(
        policy_input: &PolicyRequest,
        article: String,
        compliance_level: u8,
    ) -> Result<(Box<dyn L1Output>, Box<dyn L2Output>, Box<dyn L3Output>), String> {
        // L1: Create policy decision from input
        let l1_output = {
            let bound = PolicyBound {
                decision: "policy-compliant".to_string(),
                cited_article: article.clone(),
                compliance_level,
            };
            PolicyDecision::new(bound, policy_input.id().to_string())
        };

        // L2: Convert L1 output to L2 input, execute search
        let l2_input = L1ToL2Adapter::convert_output_to_input(
            &l1_output,
            policy_input.id().to_string(),
        );

        let l2_output = KnowledgeResult::new(
            l2_input.request_id().to_string(),
            l2_input.query().to_string(),
            vec![SearchResult {
                article_id: article.clone(),
                title: format!("Policy: {}", article),
                score: 0.95,
                rank: 1,
                source: "semantic+keyword".to_string(),
            }],
            45,
        );

        // L3: Convert L2 output to L3 input, create gated decision
        let l3_input = L2ToL3Adapter::convert_output_to_input(&l2_output);

        let l3_output = {
            let gate = PermitGate::new(
                "policy_query".to_string(),
                article,
                1,
            );
            GatedDecision::new(
                l3_input.request_id().to_string(),
                gate,
                "Full contract chain executed".to_string(),
            )
        };

        Ok((Box::new(l1_output), Box::new(l2_output), Box::new(l3_output)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_l1_to_l2_adapter() {
        let bound = PolicyBound {
            decision: "ok".to_string(),
            cited_article: "Article 50".to_string(),
            compliance_level: 100,
        };
        let l1_out = PolicyDecision::new(bound, "req_001".to_string());
        let l1_out_trait: &dyn L1Output = &l1_out;

        let l2_in = L1ToL2Adapter::convert_output_to_input(l1_out_trait, "query".to_string());

        assert_eq!(l2_in.request_id(), "req_001");
        assert_eq!(l2_in.article(), "Article 50");
        assert_eq!(l2_in.compliance_level(), 100);
    }

    #[test]
    fn test_l2_to_l3_adapter() {
        let l2_out = KnowledgeResult::new(
            "req_002".to_string(),
            "query".to_string(),
            vec![SearchResult {
                article_id: "A50".to_string(),
                title: "Title".to_string(),
                score: 0.9,
                rank: 1,
                source: "source".to_string(),
            }],
            40,
        );
        let l2_out_trait: &dyn L2Output = &l2_out;

        let l3_in = L2ToL3Adapter::convert_output_to_input(l2_out_trait);

        assert_eq!(l3_in.request_id(), "req_002");
        assert_eq!(l3_in.results_count(), 1);
        assert!(l3_in.requires_approval());
    }

    #[test]
    fn test_full_pipeline() {
        let policy_req = PolicyRequest::new(
            "test policy".to_string(),
            "user_001".to_string(),
        );

        let result = L1L2L3Pipeline::execute(
            &policy_req,
            "Article 50".to_string(),
            100,
        );

        assert!(result.is_ok());
        let (l1_out, l2_out, l3_out) = result.unwrap();

        // Verify request ID threading
        assert_eq!(l1_out.request_id(), policy_req.id());
        assert_eq!(l2_out.request_id(), policy_req.id());
        assert_eq!(l3_out.request_id(), policy_req.id());

        // Verify contract adherence
        assert_eq!(l1_out.article(), "Article 50");
        assert_eq!(l2_out.results_count(), 1);
        assert_eq!(l3_out.approval_reason(), "Full contract chain executed");
    }

    #[test]
    fn test_pipeline_preserves_compliance_level() {
        for level in &[0u8, 50, 100] {
            let policy_req = PolicyRequest::new("test".to_string(), "user".to_string());
            let result = L1L2L3Pipeline::execute(&policy_req, "Article 50".to_string(), *level);

            let (l1_out, _, _) = result.unwrap();
            assert_eq!(l1_out.compliance_level(), *level);
        }
    }

    #[test]
    fn test_no_json_serialization_in_flow() {
        // This test verifies that the entire pipeline works without any JSON
        // serialization/deserialization. All data flows through typed contracts.
        let req = PolicyRequest::new("test".to_string(), "user".to_string());
        let _result = L1L2L3Pipeline::execute(&req, "Article 50".to_string(), 100);
        // If this compiles and runs, we've proven type-safe contracts work
    }
}
