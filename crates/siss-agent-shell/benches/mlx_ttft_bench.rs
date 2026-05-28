use criterion::{black_box, criterion_group, criterion_main, Criterion};
use siss_agent_shell::rapid_mlx_integration::{
    RapidMLXEngine, RapidMLXConfig, InferenceRequest, Quantization, MlxAvailabilityProbe,
};
use uuid::Uuid;

fn default_config() -> RapidMLXConfig {
    RapidMLXConfig {
        model_name: "Qwen3.5-4B".to_string(),
        quantization: Quantization::Q4,
        context_window: 4096,
        max_tokens: 512,
        temperature: 0.7,
        top_p: 0.9,
    }
}

fn bench_ttft_fresh_inference(c: &mut Criterion) {
    if !MlxAvailabilityProbe::check() {
        return;
    }

    c.bench_function("ttft_fresh_inference", |b| {
        b.iter(|| {
            let mut engine = RapidMLXEngine::new(default_config());
            let request = InferenceRequest {
                request_id: Uuid::new_v4(),
                model_config: default_config(),
                prompt: black_box("What is the capital of France?".to_string()),
                system_prompt: None,
                tools: vec![],
                use_cached_prompt: false,
                resume_from_snapshot: None,
            };
            let _ = engine.infer(request);
        })
    });
}

fn bench_ttft_cached_prompt(c: &mut Criterion) {
    if !MlxAvailabilityProbe::check() {
        return;
    }

    c.bench_function("ttft_cached_prompt", |b| {
        b.iter(|| {
            let mut engine = RapidMLXEngine::new(default_config());
            let request = InferenceRequest {
                request_id: Uuid::new_v4(),
                model_config: default_config(),
                prompt: black_box("cached query".to_string()),
                system_prompt: None,
                tools: vec![],
                use_cached_prompt: true,
                resume_from_snapshot: None,
            };
            let _ = engine.infer(request);
        })
    });
}

fn bench_ttft_snapshot_resume(c: &mut Criterion) {
    if !MlxAvailabilityProbe::check() {
        return;
    }

    c.bench_function("ttft_snapshot_resume", |b| {
        let mut engine = RapidMLXEngine::new(default_config());
        let setup_request = InferenceRequest {
            request_id: Uuid::new_v4(),
            model_config: default_config(),
            prompt: "Initial prompt".to_string(),
            system_prompt: None,
            tools: vec![],
            use_cached_prompt: false,
            resume_from_snapshot: None,
        };

        if let Ok(response) = engine.infer(setup_request) {
            if let Some(snapshot_id) = response.snapshot_created {
                b.iter(|| {
                    let mut engine = RapidMLXEngine::new(default_config());
                    let request = InferenceRequest {
                        request_id: Uuid::new_v4(),
                        model_config: default_config(),
                        prompt: black_box("Continue from snapshot".to_string()),
                        system_prompt: None,
                        tools: vec![],
                        use_cached_prompt: false,
                        resume_from_snapshot: Some(snapshot_id),
                    };
                    let _ = engine.infer(request);
                })
            }
        }
    });
}

criterion_group!(
    benches,
    bench_ttft_fresh_inference,
    bench_ttft_cached_prompt,
    bench_ttft_snapshot_resume
);
criterion_main!(benches);
