//! Budget management and cost forecasting

use crate::error::{Error, Result};
use crate::types::{BudgetRecord, ForecastPoint};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Budget configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BudgetConfig {
    pub period_days: i64,
    pub alert_threshold_pct: f32,
    pub forecast_lookahead_days: i64,
}

impl Default for BudgetConfig {
    fn default() -> Self {
        Self {
            period_days: 30,
            alert_threshold_pct: 80.0,
            forecast_lookahead_days: 7,
        }
    }
}

/// Budgeter: cost prediction and budgeting
pub struct Budgeter {
    config: BudgetConfig,
    budgets: Arc<RwLock<HashMap<String, BudgetRecord>>>,
    historical_costs: Arc<RwLock<HashMap<String, Vec<(chrono::DateTime<chrono::Utc>, f64)>>>>,
}

impl Budgeter {
    /// Create new budgeter
    pub fn new(config: BudgetConfig) -> Self {
        Self {
            config,
            budgets: Arc::new(RwLock::new(HashMap::new())),
            historical_costs: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Create budget for agent
    pub fn create_budget(&self, agent_id: String, allocated_budget: f64) -> Result<BudgetRecord> {
        let now = chrono::Utc::now();
        let budget = BudgetRecord {
            agent_id: agent_id.clone(),
            period_start: now,
            period_end: now + chrono::Duration::days(self.config.period_days),
            allocated_budget,
            spent: 0.0,
            forecasted_final_spend: 0.0,
        };

        let mut budgets = self.budgets.write();
        budgets.insert(agent_id, budget.clone());
        Ok(budget)
    }

    /// Record cost against budget
    pub fn record_cost(&self, agent_id: &str, cost: f64) -> Result<()> {
        let mut budgets = self.budgets.write();
        let mut costs = self.historical_costs.write();

        if let Some(budget) = budgets.get_mut(agent_id) {
            budget.spent += cost;

            // Update forecast
            budget.forecasted_final_spend = self.calculate_forecast(agent_id, &costs);

            costs
                .entry(agent_id.to_string())
                .or_insert_with(Vec::new)
                .push((chrono::Utc::now(), cost));

            Ok(())
        } else {
            Err(Error::AgentNotFound(agent_id.to_string()))
        }
    }

    /// Check if budget is exceeded
    pub fn is_budget_exceeded(&self, agent_id: &str) -> bool {
        self.budgets
            .read()
            .get(agent_id)
            .map(|b| b.spent > b.allocated_budget)
            .unwrap_or(false)
    }

    /// Get budget status percentage
    pub fn get_budget_status_pct(&self, agent_id: &str) -> f32 {
        self.budgets
            .read()
            .get(agent_id)
            .map(|b| ((b.spent / b.allocated_budget) * 100.0) as f32)
            .unwrap_or(0.0)
    }

    /// Predict future costs
    pub fn predict_costs(&self, agent_id: &str) -> Result<Vec<ForecastPoint>> {
        let historical = self.historical_costs.read();

        if let Some(costs) = historical.get(agent_id) {
            if costs.is_empty() {
                return Ok(Vec::new());
            }

            let mut forecasts = Vec::new();
            let avg_daily_cost = costs.iter().map(|(_, c)| c).sum::<f64>() / costs.len() as f64;

            for i in 1..=self.config.forecast_lookahead_days {
                let timestamp = chrono::Utc::now() + chrono::Duration::days(i);
                let predicted_cost = avg_daily_cost * (1.0 + (i as f64 * 0.05)); // 5% growth per day
                let confidence = 0.8 - (i as f32 * 0.05); // Confidence decreases with time

                forecasts.push(ForecastPoint {
                    timestamp,
                    predicted_cost: predicted_cost.max(0.0),
                    confidence: confidence.max(0.1),
                });
            }

            Ok(forecasts)
        } else {
            Err(Error::AgentNotFound(agent_id.to_string()))
        }
    }

    /// Get budget record
    pub fn get_budget(&self, agent_id: &str) -> Option<BudgetRecord> {
        self.budgets.read().get(agent_id).cloned()
    }

    fn calculate_forecast(
        &self,
        agent_id: &str,
        historical: &HashMap<String, Vec<(chrono::DateTime<chrono::Utc>, f64)>>,
    ) -> f64 {
        if let Some(costs) = historical.get(agent_id) {
            if costs.is_empty() {
                return 0.0;
            }

            let avg_cost = costs.iter().map(|(_, c)| c).sum::<f64>() / costs.len() as f64;
            let days_elapsed = (chrono::Utc::now() - costs[0].0).num_days();

            if days_elapsed > 0 {
                (avg_cost / days_elapsed as f64) * self.config.period_days as f64
            } else {
                avg_cost * self.config.period_days as f64
            }
        } else {
            0.0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_budgeter_creation() {
        let budgeter = Budgeter::new(BudgetConfig::default());
        assert!(budgeter.get_budget("agent1").is_none());
    }

    #[test]
    fn test_create_budget() {
        let budgeter = Budgeter::new(BudgetConfig::default());
        let result = budgeter.create_budget("agent1".to_string(), 100.0);
        assert!(result.is_ok());

        let budget = budgeter.get_budget("agent1").unwrap();
        assert_eq!(budget.allocated_budget, 100.0);
        assert_eq!(budget.spent, 0.0);
    }

    #[test]
    fn test_record_cost() {
        let budgeter = Budgeter::new(BudgetConfig::default());
        budgeter.create_budget("agent1".to_string(), 100.0).unwrap();

        let result = budgeter.record_cost("agent1", 25.0);
        assert!(result.is_ok());

        let budget = budgeter.get_budget("agent1").unwrap();
        assert_eq!(budget.spent, 25.0);
    }

    #[test]
    fn test_budget_exceeded() {
        let budgeter = Budgeter::new(BudgetConfig::default());
        budgeter.create_budget("agent1".to_string(), 100.0).unwrap();

        budgeter.record_cost("agent1", 110.0).unwrap();
        assert!(budgeter.is_budget_exceeded("agent1"));
    }

    #[test]
    fn test_budget_status_pct() {
        let budgeter = Budgeter::new(BudgetConfig::default());
        budgeter.create_budget("agent1".to_string(), 100.0).unwrap();
        budgeter.record_cost("agent1", 50.0).unwrap();

        let status = budgeter.get_budget_status_pct("agent1");
        assert!((status - 50.0).abs() < 0.1);
    }

    #[test]
    fn test_predict_costs() {
        let budgeter = Budgeter::new(BudgetConfig::default());
        budgeter.create_budget("agent1".to_string(), 1000.0).unwrap();

        budgeter.record_cost("agent1", 10.0).unwrap();
        budgeter.record_cost("agent1", 12.0).unwrap();

        let forecast = budgeter.predict_costs("agent1").unwrap();
        assert!(!forecast.is_empty());

        for point in &forecast {
            assert!(point.predicted_cost >= 0.0);
            assert!(point.confidence > 0.0 && point.confidence <= 1.0);
        }
    }

    #[test]
    fn test_predict_nonexistent_agent() {
        let budgeter = Budgeter::new(BudgetConfig::default());
        let result = budgeter.predict_costs("nonexistent");
        assert!(result.is_err());
    }
}
