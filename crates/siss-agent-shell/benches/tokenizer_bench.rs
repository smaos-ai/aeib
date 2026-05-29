use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn tokenizer_benchmark(c: &mut Criterion) {
    c.bench_function("placeholder", |b| b.iter(|| black_box(1 + 1)));
}

criterion_group!(benches, tokenizer_benchmark);
criterion_main!(benches);
