use siss_job_router::confidence_scorer::{SimpleScorer, RoutingTier};
use siss_job_router::cost_budget::CostMatrix;
use siss_job_router::routing_engine::RoutingEngine;
use std::io::{self, BufRead};

fn main() {
    println!("🚀 Confidence-Gating Job Router v1.0");
    println!("Commands: score <task>, route <task>, budget <tokens>, exit");
    println!("---");

    let stdin = io::stdin();
    let reader = stdin.lock();

    for line in reader.lines() {
        if let Ok(input) = line {
            let trimmed = input.trim();

            match trimmed.split_whitespace().next() {
                Some("score") => {
                    let task = trimmed.strip_prefix("score ").unwrap_or("").trim();
                    if task.is_empty() {
                        println!("❌ Usage: score <task_description>");
                        continue;
                    }
                    let score = SimpleScorer::score_task(task);
                    println!("✓ Task: '{}' → Confidence: {:.2} → Tier: {:?}", task, score.score, score.recommended_tier);
                    println!("  Est. Tokens: {}", score.estimated_tokens);
                }
                Some("route") => {
                    let task = trimmed.strip_prefix("route ").unwrap_or("").trim();
                    if task.is_empty() {
                        println!("❌ Usage: route <task_description>");
                        continue;
                    }
                    let score = SimpleScorer::score_task(task);
                    match RoutingEngine::decide(&score, None) {
                        Ok(decision) => {
                            println!("✓ Task: '{}' → Primary: {:?}", task, decision.primary_tier);
                            println!("  Fallback Chain: {:?}", decision.fallback_chain);
                            println!("  Reason: {}", decision.reason);
                        }
                        Err(e) => {
                            println!("❌ Routing Error: {:?}", e);
                        }
                    }
                }
                Some("budget") => {
                    if let Some(tokens_str) = trimmed.strip_prefix("budget ") {
                        if let Ok(tokens) = tokens_str.trim().parse::<u32>() {
                            let matrix = CostMatrix::default();
                            let cost_tier1 = matrix.estimate_cost(RoutingTier::Tier1RapidMLX, tokens);
                            let cost_tier2 = matrix.estimate_cost(RoutingTier::Tier2Sonnet, tokens);
                            let cost_tier3 = matrix.estimate_cost(RoutingTier::Tier3Opus, tokens);

                            println!("✓ Token Budget Analysis: {} tokens", tokens);
                            println!("  Tier1 Cost: ${:.6}", cost_tier1);
                            println!("  Tier2 Cost: ${:.6}", cost_tier2);
                            println!("  Tier3 Cost: ${:.6}", cost_tier3);

                            let cached_cost_tier2 = matrix.estimate_cost_with_cache(RoutingTier::Tier2Sonnet, tokens, true);
                            let cached_cost_tier3 = matrix.estimate_cost_with_cache(RoutingTier::Tier3Opus, tokens, true);

                            println!("  Tier2 Cost (cached): ${:.6} (-90%)", cached_cost_tier2);
                            println!("  Tier3 Cost (cached): ${:.6} (-90%)", cached_cost_tier3);
                        } else {
                            println!("❌ Usage: budget <token_count>");
                        }
                    }
                }
                Some("exit") => {
                    println!("👋 Goodbye!");
                    break;
                }
                Some(cmd) => {
                    println!("❌ Unknown command: {}. Try: score, route, budget, exit", cmd);
                }
                None => {
                    println!("❌ Empty command");
                }
            }
        }
    }
}
