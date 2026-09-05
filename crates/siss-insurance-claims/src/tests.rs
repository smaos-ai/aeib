#[cfg(test)]
mod tests {
    use crate::*;
    use chrono::Utc;
    use uuid::Uuid;

    // ==============================================================================
    // POSTGRESQL LEDGER TESTS (1-6)
    // ==============================================================================

    #[test]
    fn test_ledger_create_claim_entry() {
        let ledger = ClaimLedger::new();
        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        let entry = ledger
            .record_claim(claim_id, policy_id, claimant_id, 50_000_00)
            .unwrap();

        assert_eq!(entry.claim_id, claim_id);
        assert_eq!(entry.policy_id, policy_id);
        assert_eq!(entry.claimant_id, claimant_id);
        assert_eq!(entry.amount_cents, 50_000_00);
        assert_eq!(entry.status, ClaimStatus::Submitted);
    }

    #[test]
    fn test_ledger_retrieve_claim() {
        let ledger = ClaimLedger::new();
        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        let _ = ledger.record_claim(claim_id, policy_id, claimant_id, 100_000_00);
        let retrieved = ledger.get_claim(&claim_id).unwrap();

        assert_eq!(retrieved.claim_id, claim_id);
        assert_eq!(retrieved.amount_cents, 100_000_00);
    }

    #[test]
    fn test_ledger_update_claim_status() {
        let ledger = ClaimLedger::new();
        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        ledger
            .record_claim(claim_id, policy_id, claimant_id, 75_000_00)
            .unwrap();
        ledger
            .update_claim_status(&claim_id, ClaimStatus::UnderReview)
            .unwrap();
        let updated = ledger.get_claim(&claim_id).unwrap();

        assert_eq!(updated.status, ClaimStatus::UnderReview);
    }

    #[test]
    fn test_ledger_list_claims_by_policy() {
        let ledger = ClaimLedger::new();
        let policy_id = Uuid::new_v4();
        let claimant1 = Uuid::new_v4();
        let claimant2 = Uuid::new_v4();

        let claim1 = Uuid::new_v4();
        let claim2 = Uuid::new_v4();

        ledger
            .record_claim(claim1, policy_id, claimant1, 50_000_00)
            .unwrap();
        ledger
            .record_claim(claim2, policy_id, claimant2, 75_000_00)
            .unwrap();

        let claims = ledger.get_claims_by_policy(&policy_id).unwrap();
        assert_eq!(claims.len(), 2);
    }

    #[test]
    fn test_ledger_claim_audit_trail() {
        let ledger = ClaimLedger::new();
        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        ledger
            .record_claim(claim_id, policy_id, claimant_id, 100_000_00)
            .unwrap();
        ledger
            .update_claim_status(&claim_id, ClaimStatus::UnderReview)
            .unwrap();
        ledger
            .update_claim_status(&claim_id, ClaimStatus::Approved)
            .unwrap();

        let history = ledger.get_claim_history(&claim_id).unwrap();
        assert!(history.len() >= 3);
        assert_eq!(history[0].status, ClaimStatus::Submitted);
        assert_eq!(history[1].status, ClaimStatus::UnderReview);
        assert_eq!(history[2].status, ClaimStatus::Approved);
    }

    // ==============================================================================
    // MERKLE TREE TESTS (7-11)
    // ==============================================================================

    #[test]
    fn test_merkle_create_leaf() {
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 50_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let leaf = MerkleLeaf::from_claim(&claim);
        assert_eq!(leaf.claim_id, claim.id);
        assert!(!leaf.hash.is_empty());
        assert_eq!(leaf.hash.len(), 64); // SHA-256 hex-encoded
    }

    #[test]
    fn test_merkle_tree_root_hash() {
        let mut tree = MerkleTree::new();

        let claim1 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 50_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let claim2 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 75_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        tree.insert(claim1.clone()).unwrap();
        tree.insert(claim2.clone()).unwrap();

        let root = tree.root_hash();
        assert!(!root.is_empty());
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_merkle_proof_generation() {
        let mut tree = MerkleTree::new();
        let claim1 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let claim2 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 150_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        tree.insert(claim1.clone()).unwrap();
        tree.insert(claim2).unwrap();

        let proof = tree.generate_proof(&claim1.id).unwrap();
        assert!(!proof.is_empty());
        assert!(proof.iter().all(|h| h.len() == 64));
    }

    #[test]
    fn test_merkle_proof_verification() {
        let mut tree = MerkleTree::new();
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 75_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        tree.insert(claim.clone()).unwrap();

        let proof = tree.generate_proof(&claim.id).unwrap();
        let leaf = MerkleLeaf::from_claim(&claim);
        let root = tree.root_hash();

        let verified = MerkleTree::verify_proof(&leaf.hash, &proof, &root).unwrap();
        assert!(verified);
    }

    // ==============================================================================
    // ZK PROOF GENERATOR TESTS (12-19)
    // ==============================================================================

    #[test]
    fn test_zk_proof_generation() {
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let proof = ZkProofGenerator::generate_claim_proof(&claim).unwrap();
        assert!(!proof.proof_data.is_empty());
        assert_eq!(proof.claim_id, claim.id);
    }

    #[test]
    fn test_zk_proof_verification() {
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 50_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let proof = ZkProofGenerator::generate_claim_proof(&claim).unwrap();
        let verified = ZkProofGenerator::verify_proof(&proof).unwrap();
        assert!(verified);
    }

    #[test]
    fn test_zk_proof_no_pii_disclosure() {
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let proof = ZkProofGenerator::generate_claim_proof(&claim).unwrap();

        // Proof should not contain raw claim amount
        let proof_str = hex::encode(&proof.proof_data);
        // Should not contain amount as plaintext
        assert!(!proof_str.contains(&format!("{:x}", claim.claim_amount)));
    }

    #[test]
    fn test_zk_proof_different_claims_different_proofs() {
        let claim1 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let claim2 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 150_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let proof1 = ZkProofGenerator::generate_claim_proof(&claim1).unwrap();
        let proof2 = ZkProofGenerator::generate_claim_proof(&claim2).unwrap();

        assert_ne!(proof1.proof_data, proof2.proof_data);
    }

    #[test]
    fn test_zk_proof_range_verification() {
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 50_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let proof = ZkProofGenerator::generate_claim_proof(&claim).unwrap();
        let in_range = ZkProofGenerator::verify_amount_range(&proof, 1_000_00, 100_000_00).unwrap();
        assert!(in_range);
    }

    #[test]
    fn test_zk_proof_batch_verification() {
        let mut claims = vec![];
        let mut proofs = vec![];

        for i in 0..3 {
            let claim = Claim {
                id: Uuid::new_v4(),
                policy_id: Uuid::new_v4(),
                claimant_sovereign_id: Uuid::new_v4(),
                claim_amount: (i + 1) as u64 * 50_000_00,
                status: ClaimStatus::Submitted,
                submitted_at: Utc::now(),
                settlement_amount: None,
                settled_at: None,
                merkle_proof: None,
            };
            let proof = ZkProofGenerator::generate_claim_proof(&claim).unwrap();
            claims.push(claim);
            proofs.push(proof);
        }

        let verified = ZkProofGenerator::verify_batch(&proofs).unwrap();
        assert!(verified);
    }

    // ==============================================================================
    // PARAMETRIC PAYOUT TESTS (20-23)
    // ==============================================================================

    #[test]
    fn test_parametric_payout_threshold_trigger() {
        let payout_engine = ParametricPayoutEngine::new();
        let claim_id = Uuid::new_v4();
        let trigger = ParametricTrigger::EventThreshold {
            event_type: "earthquake".to_string(),
            threshold: 7,
        };

        let payout = payout_engine
            .create_payout(claim_id, trigger, 100_000_00)
            .unwrap();

        assert_eq!(payout.claim_id, claim_id);
        assert_eq!(payout.payout_amount, 100_000_00);
        assert!(payout.executed_at.is_none());
    }

    #[test]
    fn test_parametric_payout_execution() {
        let payout_engine = ParametricPayoutEngine::new();
        let claim_id = Uuid::new_v4();
        let trigger = ParametricTrigger::DataFeed {
            source: "weather_api".to_string(),
            min_value: 8.5,
        };

        let payout = payout_engine
            .create_payout(claim_id, trigger, 50_000_00)
            .unwrap();

        let executed = payout_engine.execute_payout(&payout.id).unwrap();
        assert!(executed.executed_at.is_some());
    }

    #[test]
    fn test_parametric_payout_time_window() {
        let payout_engine = ParametricPayoutEngine::new();
        let claim_id = Uuid::new_v4();
        let trigger = ParametricTrigger::TimeWindow {
            start_day: 1,
            end_day: 30,
        };

        let payout = payout_engine
            .create_payout(claim_id, trigger, 75_000_00)
            .unwrap();

        assert_eq!(payout.payout_amount, 75_000_00);
    }

    #[test]
    fn test_parametric_payout_batch_settlement() {
        let payout_engine = ParametricPayoutEngine::new();

        for i in 0..5 {
            let claim_id = Uuid::new_v4();
            let trigger = ParametricTrigger::EventThreshold {
                event_type: "flood".to_string(),
                threshold: 3,
            };
            let _ = payout_engine
                .create_payout(claim_id, trigger, (i as u64 + 1) * 50_000_00)
                .unwrap();
        }

        let payouts = payout_engine.get_pending_payouts().unwrap();
        assert_eq!(payouts.len(), 5);
    }

    // ==============================================================================
    // REBAC WORKFLOW TESTS (24-29)
    // ==============================================================================

    #[test]
    fn test_rebac_role_creation() {
        let rebac = ReBAC::new();
        let role_id = Uuid::new_v4();

        let role = rebac
            .create_role(
                role_id,
                "claims_reviewer".to_string(),
                vec!["claim:read".to_string(), "claim:update".to_string()],
            )
            .unwrap();

        assert_eq!(role.role_name, "claims_reviewer");
        assert_eq!(role.permissions.len(), 2);
    }

    #[test]
    fn test_rebac_user_assignment() {
        let rebac = ReBAC::new();
        let user_id = Uuid::new_v4();
        let role_id = Uuid::new_v4();

        let _ = rebac
            .create_role(
                role_id,
                "claims_approver".to_string(),
                vec!["claim:approve".to_string()],
            )
            .unwrap();

        let assigned = rebac.assign_role_to_user(user_id, role_id).unwrap();
        assert!(assigned);
    }

    #[test]
    fn test_rebac_permission_check() {
        let rebac = ReBAC::new();
        let user_id = Uuid::new_v4();
        let role_id = Uuid::new_v4();

        let _ = rebac
            .create_role(
                role_id,
                "claims_analyst".to_string(),
                vec!["claim:read".to_string()],
            )
            .unwrap();

        rebac.assign_role_to_user(user_id, role_id).unwrap();

        let has_read = rebac.has_permission(user_id, "claim:read").unwrap();
        assert!(has_read);

        let has_approve = rebac.has_permission(user_id, "claim:approve").unwrap();
        assert!(!has_approve);
    }

    #[test]
    fn test_rebac_claim_approval_workflow() {
        let rebac = ReBAC::new();
        let _claim_id = Uuid::new_v4();
        let reviewer_id = Uuid::new_v4();
        let approver_id = Uuid::new_v4();

        let reviewer_role = Uuid::new_v4();
        let approver_role = Uuid::new_v4();

        let _ = rebac
            .create_role(
                reviewer_role,
                "claims_reviewer".to_string(),
                vec!["claim:review".to_string()],
            )
            .unwrap();
        let _ = rebac
            .create_role(
                approver_role,
                "claims_approver".to_string(),
                vec!["claim:approve".to_string()],
            )
            .unwrap();

        rebac
            .assign_role_to_user(reviewer_id, reviewer_role)
            .unwrap();
        rebac
            .assign_role_to_user(approver_id, approver_role)
            .unwrap();

        let reviewed = rebac.has_permission(reviewer_id, "claim:review").unwrap();
        let approved = rebac.has_permission(approver_id, "claim:approve").unwrap();

        assert!(reviewed);
        assert!(approved);
    }

    #[test]
    fn test_rebac_role_hierarchy() {
        let rebac = ReBAC::new();

        let basic_role = Uuid::new_v4();
        let senior_role = Uuid::new_v4();

        let _ = rebac
            .create_role(
                basic_role,
                "analyst".to_string(),
                vec!["claim:read".to_string()],
            )
            .unwrap();
        let _ = rebac
            .create_role(
                senior_role,
                "senior_analyst".to_string(),
                vec!["claim:read".to_string(), "claim:override".to_string()],
            )
            .unwrap();

        let user_id = Uuid::new_v4();
        rebac.assign_role_to_user(user_id, senior_role).unwrap();

        let has_read = rebac.has_permission(user_id, "claim:read").unwrap();
        let has_override = rebac.has_permission(user_id, "claim:override").unwrap();

        assert!(has_read);
        assert!(has_override);
    }

    // ==============================================================================
    // INTEGRATION TESTS (30-38)
    // ==============================================================================

    #[test]
    fn test_end_to_end_claim_submission() {
        let ledger = ClaimLedger::new();
        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        let entry = ledger
            .record_claim(claim_id, policy_id, claimant_id, 100_000_00)
            .unwrap();

        assert_eq!(entry.status, ClaimStatus::Submitted);
    }

    #[test]
    fn test_end_to_end_merkle_and_zk() {
        let mut tree = MerkleTree::new();
        let claim1 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 75_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let claim2 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        tree.insert(claim1.clone()).unwrap();
        tree.insert(claim2).unwrap();
        let merkle_proof = tree.generate_proof(&claim1.id).unwrap();

        let zk_proof = ZkProofGenerator::generate_claim_proof(&claim1).unwrap();
        let verified = ZkProofGenerator::verify_proof(&zk_proof).unwrap();

        assert!(!merkle_proof.is_empty());
        assert!(verified);
    }

    #[test]
    fn test_end_to_end_claim_approval_flow() {
        let ledger = ClaimLedger::new();
        let rebac = ReBAC::new();

        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();
        let reviewer_id = Uuid::new_v4();

        // Submit claim
        let _ = ledger.record_claim(claim_id, policy_id, claimant_id, 100_000_00);

        // Create reviewer role
        let role_id = Uuid::new_v4();
        let _ = rebac
            .create_role(
                role_id,
                "reviewer".to_string(),
                vec!["claim:review".to_string()],
            )
            .unwrap();

        // Assign reviewer
        rebac.assign_role_to_user(reviewer_id, role_id).unwrap();

        // Check permission
        let can_review = rebac.has_permission(reviewer_id, "claim:review").unwrap();
        assert!(can_review);

        // Update status
        ledger
            .update_claim_status(&claim_id, ClaimStatus::UnderReview)
            .unwrap();

        let updated = ledger.get_claim(&claim_id).unwrap();
        assert_eq!(updated.status, ClaimStatus::UnderReview);
    }

    #[test]
    fn test_end_to_end_parametric_settlement() {
        let ledger = ClaimLedger::new();
        let payout_engine = ParametricPayoutEngine::new();

        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        // Create claim
        let _ = ledger.record_claim(claim_id, policy_id, claimant_id, 100_000_00);

        // Create parametric payout
        let trigger = ParametricTrigger::EventThreshold {
            event_type: "hurricane".to_string(),
            threshold: 4,
        };
        let payout = payout_engine
            .create_payout(claim_id, trigger, 100_000_00)
            .unwrap();

        assert_eq!(payout.payout_amount, 100_000_00);
    }

    #[test]
    fn test_end_to_end_claim_with_merkle_zk_payout() {
        let ledger = ClaimLedger::new();
        let mut tree = MerkleTree::new();
        let payout_engine = ParametricPayoutEngine::new();

        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        let claim = Claim {
            id: claim_id,
            policy_id,
            claimant_sovereign_id: claimant_id,
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        // Record in ledger
        let _ = ledger.record_claim(claim_id, policy_id, claimant_id, 100_000_00);

        // Add to Merkle tree
        tree.insert(claim.clone()).unwrap();

        // Generate ZK proof
        let _zk_proof = ZkProofGenerator::generate_claim_proof(&claim).unwrap();

        // Create payout
        let trigger = ParametricTrigger::DataFeed {
            source: "oracle".to_string(),
            min_value: 1.0,
        };
        let payout = payout_engine
            .create_payout(claim_id, trigger, 100_000_00)
            .unwrap();

        // Verify everything is connected
        assert_eq!(payout.claim_id, claim_id);
        assert_eq!(payout.payout_amount, claim.claim_amount);
    }

    #[test]
    fn test_end_to_end_multi_claim_audit() {
        let ledger = ClaimLedger::new();

        for i in 0..5 {
            let claim_id = Uuid::new_v4();
            let policy_id = Uuid::new_v4();
            let claimant_id = Uuid::new_v4();

            ledger
                .record_claim(claim_id, policy_id, claimant_id, (i as u64 + 1) * 50_000_00)
                .unwrap();
        }

        let history = ledger.get_all_claims().unwrap();
        assert_eq!(history.len(), 5);
    }

    #[test]
    fn test_end_to_end_claim_denied_workflow() {
        let ledger = ClaimLedger::new();
        let rebac = ReBAC::new();

        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();
        let reviewer_id = Uuid::new_v4();

        // Create and submit claim
        let _ = ledger.record_claim(claim_id, policy_id, claimant_id, 100_000_00);

        // Setup reviewer
        let role_id = Uuid::new_v4();
        let _ = rebac
            .create_role(
                role_id,
                "reviewer".to_string(),
                vec!["claim:review".to_string()],
            )
            .unwrap();
        rebac.assign_role_to_user(reviewer_id, role_id).unwrap();

        // Workflow: Submitted -> UnderReview -> Denied
        ledger
            .update_claim_status(&claim_id, ClaimStatus::UnderReview)
            .unwrap();
        ledger
            .update_claim_status(&claim_id, ClaimStatus::Denied)
            .unwrap();

        let final_claim = ledger.get_claim(&claim_id).unwrap();
        assert_eq!(final_claim.status, ClaimStatus::Denied);
    }

    #[test]
    fn test_end_to_end_claim_approval_and_payment() {
        let ledger = ClaimLedger::new();

        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        // Submit
        let _ = ledger.record_claim(claim_id, policy_id, claimant_id, 100_000_00);

        // Review
        ledger
            .update_claim_status(&claim_id, ClaimStatus::UnderReview)
            .unwrap();

        // Approve
        ledger
            .update_claim_status(&claim_id, ClaimStatus::Approved)
            .unwrap();

        // Pay
        ledger.settle_claim(&claim_id, 100_000_00).unwrap();

        let final_claim = ledger.get_claim(&claim_id).unwrap();
        assert_eq!(final_claim.status, ClaimStatus::Paid);
        assert_eq!(final_claim.settlement_amount, Some(100_000_00));
    }
}
