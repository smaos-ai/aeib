use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use siss_night_cycle::operators::{NightCycleOperator, OntologyEntity, OntologyState, PhiOperator, DeltaOperator, GammaOperator};
use serde_json::json;
use std::time::Instant;

fn create_test_state(entity_count: usize) -> OntologyState {
    let mut entities = Vec::with_capacity(entity_count);
    for i in 0..entity_count {
        let id = if i % 3 == 0 { "dup".to_string() } else { format!("entity_{}", i) };
        entities.push(OntologyEntity {
            id,
            timestamp: (i as i64) * 100,
            confidence: 0.5 + (i as f64 * 0.001 % 0.5),
            data: json!({"idx": i}),
        });
    }
    OntologyState {
        entities,
        confidence_threshold: 0.6,
    }
}

fn benchmark_phi_operator(c: &mut Criterion) {
    let mut group = c.benchmark_group("phi_operator");
    for entity_count in [100, 1000, 10000].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(entity_count), entity_count, |b, &n| {
            b.iter(|| {
                let mut state = black_box(create_test_state(n));
                let phi = PhiOperator;
                phi.apply(&mut state)
            });
        });
    }
    group.finish();
}

fn benchmark_delta_operator(c: &mut Criterion) {
    let mut group = c.benchmark_group("delta_operator");
    for entity_count in [100, 1000, 10000].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(entity_count), entity_count, |b, &n| {
            b.iter(|| {
                let mut state = black_box(create_test_state(n));
                let delta = DeltaOperator;
                delta.apply(&mut state)
            });
        });
    }
    group.finish();
}

fn benchmark_gamma_operator(c: &mut Criterion) {
    let mut group = c.benchmark_group("gamma_operator");
    for entity_count in [100, 1000, 10000].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(entity_count), entity_count, |b, &n| {
            b.iter(|| {
                let mut state = black_box(create_test_state(n));
                let gamma = GammaOperator;
                gamma.apply(&mut state)
            });
        });
    }
    group.finish();
}

fn benchmark_operator_chain(c: &mut Criterion) {
    let mut group = c.benchmark_group("operator_chain");
    for entity_count in [100, 1000, 5000].iter() {
        group.bench_with_input(BenchmarkId::from_parameter(entity_count), entity_count, |b, &n| {
            b.iter(|| {
                let mut state = black_box(create_test_state(n));
                let phi = PhiOperator;
                let delta = DeltaOperator;
                let gamma = GammaOperator;

                phi.apply(&mut state);
                delta.apply(&mut state);
                gamma.apply(&mut state);
            });
        });
    }
    group.finish();
}

criterion_group!(benches, benchmark_phi_operator, benchmark_delta_operator, benchmark_gamma_operator, benchmark_operator_chain);
criterion_main!(benches);
