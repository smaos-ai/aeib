//! Integration tests for L1→L2→L3 contract chain
//! Verifies type-safe boundaries between layers with zero implicit JSON passing

#[cfg(test)]
mod contract_chain_tests {
    use l1_reasoning::{PolicyDecision, PolicyRequest, PolicyBound, L1Output};
    use l2_knowledge::{KnowledgeRequest, KnowledgeResult, L2Input, L2Output};
    use l3_permit_gates::{GateRequest, GatedDecision, L3Input, L3Output};
    use l3_permit_gates::PermitGate;

    #[test]
    fn test_l1_output_to_l2_input_contract() {
        // Create L1 output
        let bound = PolicyBound {
            decision: "allowed".to_string(),
            cited_article: "Article 50".to_string(),
            compliance_level: 100,
        };
        let l1_output = PolicyDecision::new(bound, "req_001".to_string());

        // Use L1 output to create L2 input
        let l2_input = KnowledgeRequest::new(
            l1_output.request_id().to_string(),
            l1_output.article().to_string(),
            l1_output.compliance_level(),
            "transparency requirements".to_string(),
        );

        // Verify contract preservation
        assert_eq!(l2_input.request_id(), l1_output.request_id());
        assert_eq!(l2_input.article(), l1_output.article());
        assert_eq!(l2_input.compliance_level(), l1_output.compliance_level());
    }

    #[test]
    fn test_l2_output_to_l3_input_contract() {
        // Create L2 output
        use l2_knowledge::SearchResult;
        let results = vec![SearchResult {
            article_id: "A50".to_string(),
            title: "Transparency".to_string(),
            score: 0.95,
            rank: 1,
            source: "semantic".to_string(),
        }];
        let l2_output = KnowledgeResult::new(
            "req_002".to_string(),
            "query".to_string(),
            results,
            45,
        );

        // Use L2 output to create L3 input
        let l3_input = GateRequest::new(
            l2_output.request_id().to_string(),
            l2_output.results_count(),
            l2_output.results_count() > 0,
        );

        // Verify contract preservation
        assert_eq!(l3_input.request_id(), l2_output.request_id());
        assert_eq!(l3_input.results_count(), l2_output.results_count());
    }

    #[test]
    fn test_full_l1_to_l3_chain() {
        // L1: Create policy request and decision
        let policy_req = PolicyRequest::new(
            "transparency policy".to_string(),
            "user_001".to_string(),
        );
        let l1_output = {
            let bound = PolicyBound {
                decision: "approved".to_string(),
                cited_article: "Article 50".to_string(),
                compliance_level: 100,
            };
            PolicyDecision::new(bound, policy_req.id().to_string())
        };

        // L2: Convert L1 output to L2 input, create L2 output
        let l2_input = KnowledgeRequest::new(
            l1_output.request_id().to_string(),
            l1_output.article().to_string(),
            l1_output.compliance_level(),
            "query".to_string(),
        );
        let l2_output = {
            use l2_knowledge::SearchResult;
            let results = vec![
                SearchResult {
                    article_id: "A50".to_string(),
                    title: "Transparency".to_string(),
                    score: 0.92,
                    rank: 1,
                    source: "semantic".to_string(),
                },
                SearchResult {
                    article_id: "A51".to_string(),
                    title: "Documentation".to_string(),
                    score: 0.85,
                    rank: 2,
                    source: "keyword".to_string(),
                },
            ];
            KnowledgeResult::new(
                l2_input.request_id().to_string(),
                l2_input.query().to_string(),
                results,
                50,
            )
        };

        // L3: Convert L2 output to L3 input, create L3 output
        let l3_input = GateRequest::new(
            l2_output.request_id().to_string(),
            l2_output.results_count(),
            l2_output.results_count() > 0,
        );
        let l3_output = {
            let gate = PermitGate::new(
                "knowledge_query".to_string(),
                l1_output.article().to_string(),
                1,
            );
            GatedDecision::new(
                l3_input.request_id().to_string(),
                gate,
                "Policy-approved and knowledge retrieved".to_string(),
            )
        };

        // Verify end-to-end contract
        assert_eq!(l3_output.request_id(), policy_req.id());
        assert!(l3_output.approval_reason().len() > 0);
    }

    #[test]
    fn test_l1_output_trait_object_to_l2() {
        let bound = PolicyBound {
            decision: "ok".to_string(),
            cited_article: "Article 13".to_string(),
            compliance_level: 85,
        };
        let l1_out: Box<dyn L1Output> = Box::new(PolicyDecision::new(bound, "r123".to_string()));

        // Use trait object (proves contract is dyn-safe)
        let l2_input = KnowledgeRequest::new(
            l1_out.request_id().to_string(),
            l1_out.article().to_string(),
            l1_out.compliance_level(),
            "test".to_string(),
        );

        assert_eq!(l2_input.compliance_level(), 85);
    }

    #[test]
    fn test_l2_output_trait_object_to_l3() {
        use l2_knowledge::SearchResult;
        let results = vec![SearchResult {
            article_id: "A".to_string(),
            title: "T".to_string(),
            score: 0.8,
            rank: 1,
            source: "s".to_string(),
        }];
        let l2_out: Box<dyn L2Output> = Box::new(KnowledgeResult::new(
            "r456".to_string(),
            "q".to_string(),
            results,
            30,
        ));

        // Use trait object (proves contract is dyn-safe)
        let l3_input = GateRequest::new(
            l2_out.request_id().to_string(),
            l2_out.results_count(),
            true,
        );

        assert_eq!(l3_input.request_id(), "r456");
        assert_eq!(l3_input.results_count(), 1);
    }

    #[test]
    fn test_l3_output_trait_object() {
        let gate = PermitGate::new("g".to_string(), "A".to_string(), 1);
        let l3_out: Box<dyn L3Output> = Box::new(GatedDecision::new(
            "r789".to_string(),
            gate,
            "OK".to_string(),
        ));

        assert_eq!(l3_out.request_id(), "r789");
        assert_eq!(l3_out.approval_reason(), "OK");
    }

    #[test]
    fn test_no_implicit_json_serialization() {
        // Verify we're using strong types, not JSON strings
        let bound = PolicyBound {
            decision: "test".to_string(),
            cited_article: "Article 50".to_string(),
            compliance_level: 75,
        };
        let decision = PolicyDecision::new(bound, "req".to_string());

        // No to_string() conversion to JSON needed
        let _l2_input = KnowledgeRequest::new(
            decision.request_id().to_string(), // Strong string, not JSON
            decision.article().to_string(),
            decision.compliance_level(),
            "query".to_string(),
        );

        // Compile-time type safety verified
    }

    #[test]
    fn test_request_id_threading() {
        let policy_req = PolicyRequest::new("policy".to_string(), "user".to_string());
        let req_id = policy_req.id().to_string();

        let l1_out = {
            let bound = PolicyBound {
                decision: "ok".to_string(),
                cited_article: "Article 50".to_string(),
                compliance_level: 100,
            };
            PolicyDecision::new(bound, req_id.clone())
        };

        let l2_input = KnowledgeRequest::new(
            l1_out.request_id().to_string(),
            l1_out.article().to_string(),
            100,
            "q".to_string(),
        );

        use l2_knowledge::SearchResult;
        let l2_out = KnowledgeResult::new(
            l2_input.request_id().to_string(),
            l2_input.query().to_string(),
            vec![],
            0,
        );

        let l3_input = GateRequest::new(
            l2_out.request_id().to_string(),
            0,
            false,
        );

        // Request ID preserved through entire chain
        assert_eq!(l3_input.request_id(), req_id);
    }

    #[test]
    fn test_compliance_level_preserved() {
        for level in &[0u8, 25, 50, 75, 100] {
            let bound = PolicyBound {
                decision: "test".to_string(),
                cited_article: "Article 50".to_string(),
                compliance_level: *level,
            };
            let l1_out = PolicyDecision::new(bound, "r".to_string());

            let l2_input = KnowledgeRequest::new(
                "r".to_string(),
                l1_out.article().to_string(),
                l1_out.compliance_level(),
                "q".to_string(),
            );

            // Compliance level preserved through boundary
            assert_eq!(l2_input.compliance_level(), *level);
        }
    }

    #[test]
    fn test_article_reference_chain() {
        let articles = vec!["Article 50", "Article 13", "Article 6"];

        for article in articles {
            let bound = PolicyBound {
                decision: "test".to_string(),
                cited_article: article.to_string(),
                compliance_level: 100,
            };
            let l1_out = PolicyDecision::new(bound, "r".to_string());

            let l2_input = KnowledgeRequest::new(
                "r".to_string(),
                l1_out.article().to_string(),
                100,
                "q".to_string(),
            );

            // Article preserved
            assert_eq!(l2_input.article(), article);
        }
    }

    #[test]
    fn test_gate_decision_determination() {
        let gate = PermitGate::new("g".to_string(), "A".to_string(), 1);
        let l3_out = GatedDecision::new("r".to_string(), gate, "pending".to_string());

        // Decision state accessible
        assert_eq!(l3_out.gate_decision(), l3_permit_gates::GateDecision::PendingApproval);
    }

    #[test]
    fn test_multiple_concurrent_chains() {
        // Simulate multiple requests flowing through chain simultaneously
        for i in 0..5 {
            let req_id = format!("req_{}", i);

            let bound = PolicyBound {
                decision: "ok".to_string(),
                cited_article: "Article 50".to_string(),
                compliance_level: 100,
            };
            let l1_out = PolicyDecision::new(bound, req_id.clone());

            let l2_input = KnowledgeRequest::new(
                l1_out.request_id().to_string(),
                l1_out.article().to_string(),
                100,
                format!("query_{}", i),
            );

            use l2_knowledge::SearchResult;
            let l2_out = KnowledgeResult::new(
                l2_input.request_id().to_string(),
                l2_input.query().to_string(),
                vec![SearchResult {
                    article_id: format!("A{}", i),
                    title: format!("Title{}", i),
                    score: 0.8,
                    rank: 1,
                    source: "test".to_string(),
                }],
                10 * (i as u64),
            );

            let l3_input = GateRequest::new(
                l2_out.request_id().to_string(),
                1,
                true,
            );

            // Each request maintains its own identity
            assert_eq!(l3_input.request_id(), format!("req_{}", i));
        }
    }
}
