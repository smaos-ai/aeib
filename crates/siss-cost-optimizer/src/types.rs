//! Core types for cost optimization

use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Transaction cost record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostRecord {
    pub id: Uuid,
    pub agent_id: String,
    pub transaction_id: String,
    pub cost_usd: f64,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub resource_type: String,
}

/// Agent resource allocation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentAllocation {
    pub agent_id: String,
    pub cpu_percent: f32,
    pub memory_mb: u32,
    pub bandwidth_mbps: u32,
    pub cost_budget_usd: f64,
}

/// Budget record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BudgetRecord {
    pub agent_id: String,
    pub period_start: chrono::DateTime<chrono::Utc>,
    pub period_end: chrono::DateTime<chrono::Utc>,
    pub allocated_budget: f64,
    pub spent: f64,
    pub forecasted_final_spend: f64,
}

/// Cost metric
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct CostMetric {
    pub min_cost: f64,
    pub max_cost: f64,
    pub avg_cost: f64,
    pub total_cost: f64,
    pub transaction_count: u64,
}

/// Resource requirement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceRequirement {
    pub min_cpu_percent: f32,
    pub min_memory_mb: u32,
    pub min_bandwidth_mbps: u32,
}

/// Forecast datapoint
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForecastPoint {
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub predicted_cost: f64,
    pub confidence: f32,
}
