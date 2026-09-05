use chrono::Utc;
use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use siss_layer00::{sha256, DashMapStore, Layer0Gate, Mandate, SovereignKeypair};
use std::sync::Arc;
use uuid::Uuid;

fn create_test_mandate(keypair: &SovereignKeypair, actions: Vec<String>) -> Mandate {
    let intent_hash = sha256(b"test_intent");
    let public_key = keypair.public_key_bytes();
    let signature = keypair.sign(&intent_hash);

    Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "US".to_string(),
        action_scope: actions,
        created_at: Utc::now(),
        expires_at: Utc::now() + chrono::Duration::hours(1),
    }
}

fn benchmark_gate_operations(c: &mut Criterion) {
    let mut group = c.benchmark_group("gate_operations");
    group.measurement_time(std::time::Duration::from_secs(10));
    group.sample_size(100);

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store.clone());
    let keypair = SovereignKeypair::generate();

    // Benchmark 1: Mandate registration
    group.bench_function("mandate_registration", |b| {
        let mandate = black_box(create_test_mandate(&keypair, vec!["read".to_string()]));
        b.iter(|| {
            let m = create_test_mandate(&keypair, vec!["read".to_string()]);
            gate.register_mandate(m)
        });
    });

    // Benchmark 2: Capability token request
    group.bench_function("capability_token_request", |b| {
        let mandate = create_test_mandate(&keypair, vec!["read".to_string()]);
        let mandate_id = gate.register_mandate(mandate).unwrap();

        b.iter(|| {
            let _ = gate.request_capability(black_box(mandate_id), "read");
        });
    });

    // Benchmark 3: Tool invocation
    group.bench_function("tool_invocation", |b| {
        let mandate = create_test_mandate(&keypair, vec!["execute".to_string()]);
        let mandate_id = gate.register_mandate(mandate).unwrap();
        let token = gate.request_capability(mandate_id, "execute").unwrap();

        b.iter(|| {
            let _ = gate.invoke_tool(&token, "test_tool", black_box([42u8; 32]));
        });
    });

    // Benchmark 4: Mandate validation (signature verification)
    group.bench_function("mandate_validation", |b| {
        let mandate = create_test_mandate(&keypair, vec!["read".to_string()]);
        let _ = gate.register_mandate(mandate.clone()).unwrap();

        b.iter(|| mandate.validate());
    });

    group.finish();
}

fn benchmark_merkle_chain(c: &mut Criterion) {
    let mut group = c.benchmark_group("merkle_chain");
    group.measurement_time(std::time::Duration::from_secs(15));
    group.sample_size(50);

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    let keypair = SovereignKeypair::generate();

    let mandate = create_test_mandate(&keypair, vec!["execute".to_string()]);
    let mandate_id = gate.register_mandate(mandate).unwrap();
    let token = gate.request_capability(mandate_id, "execute").unwrap();

    // Build chain of 100 entries
    for i in 0..100 {
        let _ = gate.invoke_tool(
            &token,
            &format!("tool_{}", i),
            sha256(&format!("result_{}", i).as_bytes()),
        );
    }

    group.bench_function("merkle_chain_100_entries_verify", |b| {
        b.iter(|| {
            let _ = gate.verify_chain();
        });
    });

    group.bench_function("merkle_chain_100_entries_root", |b| {
        b.iter(|| {
            let _ = gate.merkle_root();
        });
    });

    group.finish();

    // Test with 1000 entries
    let mut group = c.benchmark_group("merkle_chain_large");
    group.measurement_time(std::time::Duration::from_secs(20));
    group.sample_size(30);

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    let keypair = SovereignKeypair::generate();

    let mandate = create_test_mandate(&keypair, vec!["execute".to_string()]);
    let mandate_id = gate.register_mandate(mandate).unwrap();
    let token = gate.request_capability(mandate_id, "execute").unwrap();

    // Build chain of 1000 entries
    for i in 0..1000 {
        let _ = gate.invoke_tool(
            &token,
            &format!("tool_{}", i),
            sha256(&format!("result_{}", i).as_bytes()),
        );
    }

    group.bench_function("merkle_chain_1000_entries_verify", |b| {
        b.iter(|| {
            let _ = gate.verify_chain();
        });
    });

    group.bench_function("merkle_chain_1000_entries_root", |b| {
        b.iter(|| {
            let _ = gate.merkle_root();
        });
    });

    group.finish();
}

fn benchmark_capability_scope(c: &mut Criterion) {
    let mut group = c.benchmark_group("capability_scope");
    group.measurement_time(std::time::Duration::from_secs(10));
    group.sample_size(100);

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    let keypair = SovereignKeypair::generate();

    // Test with single action
    let mandate_single = create_test_mandate(&keypair, vec!["read".to_string()]);
    let mandate_id_single = gate.register_mandate(mandate_single).unwrap();

    // Test with wildcard actions
    let mandate_wildcard = create_test_mandate(
        &keypair,
        vec!["api.read.*".to_string(), "api.write.*".to_string()],
    );
    let mandate_id_wildcard = gate.register_mandate(mandate_wildcard).unwrap();

    group.bench_function("single_action_allowed", |b| {
        b.iter(|| gate.request_capability(black_box(mandate_id_single), "read"));
    });

    group.bench_function("wildcard_action_allowed", |b| {
        b.iter(|| gate.request_capability(black_box(mandate_id_wildcard), "api.read.user"));
    });

    group.finish();
}

criterion_group!(
    benches,
    benchmark_gate_operations,
    benchmark_merkle_chain,
    benchmark_capability_scope,
);

criterion_main!(benches);
