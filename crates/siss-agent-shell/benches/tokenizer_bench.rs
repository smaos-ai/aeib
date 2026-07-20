use criterion::{Criterion, black_box, criterion_group, criterion_main};

// Sample SMAOS Capsule text for tokenization benchmarks
const CAPSULE_TEXT: &str = r#"
This is a test Capsule content with semantic meaning.
It should be tokenized efficiently for the SMAOS Night Cycle.
The tokenizer is a critical path for inference latency.
Perplexity claims 5x improvement over Hugging Face.
We benchmark both to validate the claim.

The agent-native OS paradigm shifts OS design fundamentally.
SMAOS provides governance across all future OSes.
Human Gate ensures fail-closed semantics everywhere.

Key architectural principles for agentic systems:
1. Distributed trust across multiple verification layers
2. Fail-closed behavior by default across all boundaries
3. Semantic capsule boundaries with strict isolation guarantees
4. Human governance checkpoints at critical decision points
5. Rapid recovery with formal verification of state transitions

The Night Cycle orchestrates multi-region reconciliation:
- Collects telemetry from edge agents
- Computes policy decisions at sovereign gateways
- Routes governance decisions to local enforcement points
- Validates cryptographic proofs for all state transitions
- Ensures atomic consistency across policy domains

Tokenization performance directly impacts:
- Inference latency for policy decisions
- Throughput of Capsule processing during night cycles
- Cost of running distributed governance checkpoints
- Overall system responsiveness to changing threat models
"#;

fn bench_huggingface_tokenizer(c: &mut Criterion) {
    c.bench_function("huggingface_tokenize_capsule", |b| {
        let text = black_box(CAPSULE_TEXT);

        b.iter(|| {
            // Placeholder: simulates tokenization by whitespace splitting
            // In production, this would use: tokenizers::Tokenizer::from_pretrained(...)
            let tokens: Vec<&str> = text.split_whitespace().collect();
            tokens.len()
        });
    });
}

fn bench_perplexity_tokenizer(c: &mut Criterion) {
    c.bench_function("perplexity_tokenize_capsule", |b| {
        let text = black_box(CAPSULE_TEXT);

        b.iter(|| {
            // Placeholder: simulates Perplexity unigram tokenizer
            // Perplexity's implementation uses BPE with optimized byte-level encoding
            // Expected: ~5x faster than HuggingFace on the same text
            let tokens: Vec<&str> = text.split_whitespace().collect();
            tokens.len()
        });
    });
}

fn bench_tokenize_large_document(c: &mut Criterion) {
    c.bench_function("perplexity_tokenize_large_document", |b| {
        // Simulate a larger document (SMAOS policy memo)
        let large_text = black_box(CAPSULE_TEXT.repeat(10));

        b.iter(|| {
            let tokens: Vec<&str> = large_text.split_whitespace().collect();
            tokens.len()
        });
    });
}

fn bench_tokenize_with_special_tokens(c: &mut Criterion) {
    // Test tokenization with special SMAOS markers
    let text_with_markers = black_box(format!(
        "{}{}{}{}",
        "[CAPSULE_START]\n", CAPSULE_TEXT, "\n[POLICY_GATE]\n", CAPSULE_TEXT
    ));

    c.bench_function("perplexity_tokenize_with_markers", |b| {
        b.iter(|| {
            let tokens: Vec<&str> = text_with_markers.split_whitespace().collect();
            tokens.len()
        });
    });
}

criterion_group!(
    benches,
    bench_huggingface_tokenizer,
    bench_perplexity_tokenizer,
    bench_tokenize_large_document,
    bench_tokenize_with_special_tokens
);
criterion_main!(benches);
