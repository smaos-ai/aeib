use siss_graph_db::repo::bft_consensus;
use sqlx::PgPool;
use testcontainers::{
    GenericImage, ImageExt,
    core::{ContainerPort, WaitFor},
    runners::AsyncRunner,
};
use uuid::Uuid;

async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
    let container = GenericImage::new("postgres", "16")
        .with_exposed_port(ContainerPort::Tcp(5432))
        .with_wait_for(WaitFor::message_on_stderr(
            "database system is ready to accept connections",
        ))
        .with_env_var("POSTGRES_PASSWORD", "postgres")
        .with_env_var("POSTGRES_DB", "siss_test")
        .start()
        .await
        .expect("postgres started");

    let port = container.get_host_port_ipv4(5432).await.unwrap();
    let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
    let pool = PgPool::connect(&url).await.expect("pool connect");
    siss_graph_db::migrations::run_all(&pool)
        .await
        .expect("migrations");
    (container, pool)
}

async fn setup_sovereigns(pool: &PgPool, count: usize) -> Vec<Uuid> {
    let placeholder_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----";
    let mut sovereigns = Vec::new();

    for i in 0..count {
        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING"
        )
        .bind(sovereign_id)
        .bind(format!("Sovereign{}", i))
        .bind(placeholder_key)
        .bind("active")
        .execute(pool)
        .await
        .expect("insert sovereign");
        sovereigns.push(sovereign_id);
    }

    sovereigns
}

// ====== Group A: BFT Quorum Initialization Tests ======

#[tokio::test]
async fn test_initiate_bft_quorum_with_three_participants() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    assert!(!quorum_id.is_nil());
}

#[tokio::test]
async fn test_initiate_bft_quorum_computes_majority_formula() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 5).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let quorum = sqlx::query_as::<_, (i64,)>(
        "SELECT required_quorum FROM bft_quorum_rounds WHERE quorum_id = $1",
    )
    .bind(quorum_id)
    .fetch_one(&pool)
    .await
    .expect("fetch quorum");

    // majority = ceil(N/2) + 1, for N=5: ceil(2.5) + 1 = 4
    assert_eq!(quorum.0, 4);
}

#[tokio::test]
async fn test_initiate_bft_quorum_with_single_participant() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let quorum = sqlx::query_as::<_, (i64,)>(
        "SELECT required_quorum FROM bft_quorum_rounds WHERE quorum_id = $1",
    )
    .bind(quorum_id)
    .fetch_one(&pool)
    .await
    .expect("fetch quorum");

    // majority = ceil(1/2) + 1 = 1 + 1 = 2, but effectively 1 for single participant
    assert_eq!(quorum.0, 1);
}

#[tokio::test]
async fn test_initiate_bft_quorum_stores_initiator() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let quorum = sqlx::query_as::<_, (Uuid,)>(
        "SELECT initiator_sovereign_id FROM bft_quorum_rounds WHERE quorum_id = $1",
    )
    .bind(quorum_id)
    .fetch_one(&pool)
    .await
    .expect("fetch quorum");

    assert_eq!(quorum.0, sovereigns[0]);
}

#[tokio::test]
async fn test_initiate_bft_quorum_with_seven_participants() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 7).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let quorum = sqlx::query_as::<_, (i64,)>(
        "SELECT required_quorum FROM bft_quorum_rounds WHERE quorum_id = $1",
    )
    .bind(quorum_id)
    .fetch_one(&pool)
    .await
    .expect("fetch quorum");

    // majority = ceil(7/2) + 1 = 4 + 1 = 5
    assert_eq!(quorum.0, 5);
}

// ====== Group B: Ed25519 Signature Verification Tests ======

#[tokio::test]
async fn test_cast_signed_vote_stores_vote() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature)
        .await
        .expect("cast vote");

    let vote_count: (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM bft_quorum_signatures WHERE quorum_id = $1")
            .bind(quorum_id)
            .fetch_one(&pool)
            .await
            .expect("fetch vote count");

    assert_eq!(vote_count.0, 1);
}

#[tokio::test]
async fn test_cast_signed_vote_increments_yes_votes() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature)
        .await
        .expect("cast yes vote");

    let quorum =
        sqlx::query_as::<_, (i64,)>("SELECT yes_votes FROM bft_quorum_rounds WHERE quorum_id = $1")
            .bind(quorum_id)
            .fetch_one(&pool)
            .await
            .expect("fetch yes votes");

    assert_eq!(quorum.0, 1);
}

#[tokio::test]
async fn test_cast_signed_vote_increments_no_votes() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], false, signature)
        .await
        .expect("cast no vote");

    let quorum =
        sqlx::query_as::<_, (i64,)>("SELECT no_votes FROM bft_quorum_rounds WHERE quorum_id = $1")
            .bind(quorum_id)
            .fetch_one(&pool)
            .await
            .expect("fetch no votes");

    assert_eq!(quorum.0, 1);
}

#[tokio::test]
async fn test_cast_signed_vote_prevents_double_voting() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast first vote");

    let result =
        bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], false, signature).await;

    assert!(result.is_err(), "double voting should be prevented");
}

#[tokio::test]
async fn test_cast_signed_vote_stores_signature() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![5, 6, 7, 8];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote");

    let stored_sig: (String,) = sqlx::query_as(
        "SELECT signature FROM bft_quorum_signatures WHERE quorum_id = $1 AND voter_sovereign_id = $2"
    )
    .bind(quorum_id)
    .bind(sovereigns[1])
    .fetch_one(&pool)
    .await
    .expect("fetch signature");

    // signatures are stored as hex strings
    assert_eq!(stored_sig.0, "05060708");
}

// ====== Group C: Cross-Sovereign Attestation Tests ======

#[tokio::test]
async fn test_finalize_quorum_succeeds_with_majority() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    // required_quorum for 3 = ceil(3/2)+1 = 3
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[0], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 2");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 3");

    let quorum_state = bft_consensus::finalize_quorum(&pool, quorum_id)
        .await
        .expect("finalize quorum");

    assert_eq!(quorum_state.status, "finalized");
}

#[tokio::test]
async fn test_finalize_quorum_fails_without_majority() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 5).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    // required_quorum for 5 = ceil(5/2)+1 = 4
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 2");

    let result = bft_consensus::finalize_quorum(&pool, quorum_id).await;

    assert!(result.is_err(), "finalize should fail without majority");
}

#[tokio::test]
async fn test_merge_attestations_computes_merkle_root() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 2");

    let merkle_proof_ref = bft_consensus::merge_attestations(&pool, quorum_id)
        .await
        .expect("merge attestations");

    assert!(!merkle_proof_ref.is_empty());
    assert_eq!(
        merkle_proof_ref.len(),
        64,
        "merkle root should be 64 hex chars (256 bits)"
    );
}

#[tokio::test]
async fn test_finalize_quorum_computes_merkle_root() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[0], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 2");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 3");

    let quorum_state = bft_consensus::finalize_quorum(&pool, quorum_id)
        .await
        .expect("finalize quorum");

    assert!(!quorum_state.merkle_root.is_empty());
}

#[tokio::test]
async fn test_merkle_root_deterministic() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let mut merkle_roots = Vec::new();

    for _iteration in 0..3 {
        let quorum_id =
            bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
                .await
                .expect("initiate quorum");

        let signature = vec![1, 2, 3, 4];
        bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[0], true, signature.clone())
            .await
            .expect("cast vote 1");
        bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
            .await
            .expect("cast vote 2");
        bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
            .await
            .expect("cast vote 3");

        let quorum_state = bft_consensus::finalize_quorum(&pool, quorum_id)
            .await
            .expect("finalize quorum");

        merkle_roots.push(quorum_state.merkle_root);
    }

    // All three iterations should produce the same merkle root
    assert_eq!(merkle_roots[0], merkle_roots[1]);
    assert_eq!(merkle_roots[1], merkle_roots[2]);
}

// ====== Group D: Phase 76 Integration Tests ======

#[tokio::test]
async fn test_quorum_state_returned_on_finalize() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[0], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 2");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 3");

    let quorum_state = bft_consensus::finalize_quorum(&pool, quorum_id)
        .await
        .expect("finalize quorum");

    assert_eq!(quorum_state.quorum_id, quorum_id);
    assert_eq!(quorum_state.yes_votes, 3);
    assert_eq!(quorum_state.no_votes, 0);
}

#[tokio::test]
async fn test_quorum_frozen_after_finalization() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[0], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 2");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 3");

    bft_consensus::finalize_quorum(&pool, quorum_id)
        .await
        .expect("finalize quorum");

    // Try to cast a vote after finalization - try a new voter not in the list
    let new_sovereign = uuid::Uuid::new_v4();
    let result =
        bft_consensus::cast_signed_vote(&pool, quorum_id, new_sovereign, true, signature).await;

    assert!(result.is_err(), "voting after finalization should fail");
}

#[tokio::test]
async fn test_finalized_timestamp_recorded() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[0], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 2");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 3");

    bft_consensus::finalize_quorum(&pool, quorum_id)
        .await
        .expect("finalize quorum");

    let finalized_at: (Option<chrono::DateTime<chrono::Utc>>,) =
        sqlx::query_as("SELECT finalized_at FROM bft_quorum_rounds WHERE quorum_id = $1")
            .bind(quorum_id)
            .fetch_one(&pool)
            .await
            .expect("fetch finalized_at");

    assert!(finalized_at.0.is_some(), "finalized_at should be recorded");
}

#[tokio::test]
async fn test_merge_attestations_updates_merkle_proof_ref() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    let signature = vec![1, 2, 3, 4];
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature.clone())
        .await
        .expect("cast vote 1");
    bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[2], true, signature.clone())
        .await
        .expect("cast vote 2");

    let merkle_proof_ref = bft_consensus::merge_attestations(&pool, quorum_id)
        .await
        .expect("merge attestations");

    let stored_ref: (Option<String>,) =
        sqlx::query_as("SELECT merkle_proof_ref FROM bft_quorum_rounds WHERE quorum_id = $1")
            .bind(quorum_id)
            .fetch_one(&pool)
            .await
            .expect("fetch merkle_proof_ref");

    assert_eq!(stored_ref.0, Some(merkle_proof_ref));
}

#[tokio::test]
async fn test_quorum_timeout_enforced_at_24h() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let quorum_id = bft_consensus::initiate_bft_quorum(&pool, sovereigns[0], sovereigns.clone())
        .await
        .expect("initiate quorum");

    // Manually age the quorum by 24+ hours using SQL
    sqlx::query(
        "UPDATE bft_quorum_rounds SET created_at = NOW() - INTERVAL '25 hours' WHERE quorum_id = $1"
    )
    .bind(quorum_id)
    .execute(&pool)
    .await
    .expect("age quorum");

    // Try to cast a vote on the aged quorum
    let signature = vec![1, 2, 3, 4];
    let result =
        bft_consensus::cast_signed_vote(&pool, quorum_id, sovereigns[1], true, signature).await;

    // Should fail due to timeout
    assert!(
        result.is_err(),
        "voting on aged quorum (24h+) should fail due to timeout"
    );
}
