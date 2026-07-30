use crate::{PiPlusPlusEngine, ProofObject};

/// Verify a batch of proof objects, optionally in parallel.
///
/// Returns a Vec of Result<(), String> where each element corresponds to a proof.
/// Ok() indicates the proof passed validation, Err() indicates validation failure.
pub fn verify_proof_batch(
    engine: &PiPlusPlusEngine,
    proofs: Vec<ProofObject>,
    parallel: bool,
) -> Vec<Result<(), String>> {
    if parallel && proofs.len() > 100 {
        // Only use parallel for batches larger than 100 to avoid thread overhead
        use rayon::prelude::*;
        proofs
            .par_iter()
            .map(|proof| engine.validate_proof(proof))
            .collect()
    } else {
        // Sequential for small batches and when parallel is false
        proofs
            .iter()
            .map(|proof| engine.validate_proof(proof))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{create_signing_key, create_test_projection, create_test_transformation};
    use uuid::Uuid;

    #[test]
    fn test_batch_100_valid_proofs_under_50ms() {
        let engine = PiPlusPlusEngine::new(create_signing_key(), Uuid::new_v4());

        // Generate 100 valid proofs
        let start_gen = Instant::now();
        let mut proofs = Vec::new();
        for _ in 0..100 {
            let transformation = create_test_transformation();
            let justification = create_test_projection();
            let attestation = "valid_batch_proof".to_string();
            let proof = engine
                .generate_proof(transformation, justification, attestation)
                .expect("Proof generation must succeed");
            proofs.push(proof);
        }
        let gen_duration = start_gen.elapsed();
        println!("Generated 100 proofs in {:?}", gen_duration);

        // Verify batch
        let start_verify = Instant::now();
        let results = verify_proof_batch(&engine, proofs, false);
        let verify_duration = start_verify.elapsed();

        // All results must be Ok
        for (i, result) in results.iter().enumerate() {
            assert!(
                result.is_ok(),
                "Proof {} verification failed: {:?}",
                i,
                result
            );
        }

        // Total verification time must be under 50ms
        assert!(
            verify_duration.as_millis() < 50,
            "Batch verification took {:?} ms, expected < 50ms",
            verify_duration.as_millis()
        );
    }

    #[test]
    fn test_single_invalid_proof_isolated() {
        let engine = PiPlusPlusEngine::new(create_signing_key(), Uuid::new_v4());

        // Create 10 valid proofs
        let mut proofs = Vec::new();
        for _ in 0..10 {
            let transformation = create_test_transformation();
            let justification = create_test_projection();
            let attestation = "valid_proof".to_string();
            let proof = engine
                .generate_proof(transformation, justification, attestation)
                .expect("Proof generation must succeed");
            proofs.push(proof);
        }

        // Add 1 tampered proof (change confidence to be below threshold)
        let transformation = create_test_transformation();
        let mut tampered_justification = create_test_projection();
        tampered_justification.confidence = 0.5; // Below 0.8 threshold
        let attestation = "tampered_proof".to_string();
        let tampered_proof = engine
            .generate_proof(transformation, tampered_justification, attestation)
            .expect("Proof generation must succeed");
        proofs.push(tampered_proof);

        // Verify batch
        let results = verify_proof_batch(&engine, proofs, false);

        // Should have 11 results
        assert_eq!(results.len(), 11, "Should have 11 results");

        // Count Ok and Err
        let ok_count = results.iter().filter(|r| r.is_ok()).count();
        let err_count = results.iter().filter(|r| r.is_err()).count();

        // First 10 should be Ok, last 1 should be Err
        assert_eq!(ok_count, 10, "Expected 10 Ok results, got {}", ok_count);
        assert_eq!(err_count, 1, "Expected 1 Err result, got {}", err_count);

        // Verify the tampered proof is the one that failed
        assert!(
            results[10].is_err(),
            "The tampered proof (index 10) must fail validation"
        );
    }

    #[test]
    fn test_parallel_not_slower_than_sequential() {
        let engine = PiPlusPlusEngine::new(create_signing_key(), Uuid::new_v4());

        // Generate 50 valid proofs
        let mut proofs = Vec::new();
        for _ in 0..50 {
            let transformation = create_test_transformation();
            let justification = create_test_projection();
            let attestation = "perf_test_proof".to_string();
            let proof = engine
                .generate_proof(transformation, justification, attestation)
                .expect("Proof generation must succeed");
            proofs.push(proof);
        }

        // Time sequential verification
        let proofs_seq = proofs.clone();
        let start_seq = Instant::now();
        let results_seq = verify_proof_batch(&engine, proofs_seq, false);
        let seq_duration = start_seq.elapsed();

        // Time parallel verification
        let proofs_par = proofs.clone();
        let start_par = Instant::now();
        let results_par = verify_proof_batch(&engine, proofs_par, true);
        let par_duration = start_par.elapsed();

        // Both should produce valid results
        assert_eq!(results_seq.len(), 50, "Sequential should return 50 results");
        assert_eq!(results_par.len(), 50, "Parallel should return 50 results");

        println!("Sequential duration: {:?}", seq_duration);
        println!("Parallel duration: {:?}", par_duration);

        // Parallel should not be significantly slower than sequential
        // Allow up to 1.2x overhead for synchronization
        let max_allowed = seq_duration.as_millis() as f64 * 1.2;
        let par_millis = par_duration.as_millis() as f64;

        assert!(
            par_millis <= max_allowed,
            "Parallel ({:.2}ms) should not be slower than 1.2x sequential ({:.2}ms)",
            par_millis,
            max_allowed
        );
    }
}
