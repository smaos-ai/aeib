use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Execution cost breakdown
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct ExecutionCost {
    pub spread_cost_eur: f64,        // Bid-ask spread
    pub market_impact_eur: f64,      // Price impact from order size
    pub commission_eur: f64,         // Explicit commission
    pub fees_eur: f64,               // Regulatory or exchange fees
    pub total_cost_eur: f64,         // Total transaction cost
    pub cost_as_percentage: f64,     // As % of executed value
}

impl ExecutionCost {
    pub fn new(
        spread_cost: f64,
        market_impact: f64,
        commission: f64,
        fees: f64,
        executed_value: f64,
    ) -> Self {
        let total = spread_cost + market_impact + commission + fees;
        let percentage = if executed_value > 0.0 {
            (total / executed_value) * 100.0
        } else {
            0.0
        };

        Self {
            spread_cost_eur: spread_cost,
            market_impact_eur: market_impact,
            commission_eur: commission,
            fees_eur: fees,
            total_cost_eur: total,
            cost_as_percentage: percentage,
        }
    }

    /// Breakdown in basis points
    pub fn cost_in_bps(&self, executed_value: f64) -> f64 {
        if executed_value > 0.0 {
            (self.total_cost_eur / executed_value) * 10000.0
        } else {
            0.0
        }
    }

    /// Check if cost is within acceptable limits (< 1% for retail)
    pub fn is_acceptable_for_retail(&self) -> bool {
        self.cost_as_percentage < 1.0
    }

    /// Check if cost is within professional limits (< 0.5%)
    pub fn is_acceptable_for_professional(&self) -> bool {
        self.cost_as_percentage < 0.5
    }
}

/// Cost analysis record for MiFID II reporting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostAnalysisRecord {
    pub id: Uuid,
    pub order_id: Uuid,
    pub venue_id: Uuid,
    pub cost: ExecutionCost,
    pub executed_quantity: u64,
    pub executed_price_eur: f64,
    pub analysis_date: DateTime<Utc>,
}

impl CostAnalysisRecord {
    pub fn new(
        order_id: Uuid,
        venue_id: Uuid,
        cost: ExecutionCost,
        executed_quantity: u64,
        executed_price_eur: f64,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            order_id,
            venue_id,
            cost,
            executed_quantity,
            executed_price_eur,
            analysis_date: Utc::now(),
        }
    }

    pub fn executed_value_eur(&self) -> f64 {
        self.executed_quantity as f64 * self.executed_price_eur
    }
}

/// Cost analyzer for best execution and MiFID II reporting
pub struct CostAnalyzer {
    records: dashmap::DashMap<Uuid, CostAnalysisRecord>,
}

impl CostAnalyzer {
    pub fn new() -> Self {
        Self {
            records: dashmap::DashMap::new(),
        }
    }

    pub fn add_record(&self, record: CostAnalysisRecord) {
        self.records.insert(record.id, record);
    }

    pub fn get_record(&self, record_id: Uuid) -> Option<CostAnalysisRecord> {
        self.records.get(&record_id).map(|r| r.clone())
    }

    pub fn get_records_for_order(&self, order_id: Uuid) -> Vec<CostAnalysisRecord> {
        self.records
            .iter()
            .filter(|r| r.order_id == order_id)
            .map(|r| r.clone())
            .collect()
    }

    /// Calculate average cost across all fills for an order
    pub fn average_cost_for_order(&self, order_id: Uuid) -> Option<ExecutionCost> {
        let records = self.get_records_for_order(order_id);
        if records.is_empty() {
            return None;
        }

        let total_spread: f64 = records.iter().map(|r| r.cost.spread_cost_eur).sum();
        let total_impact: f64 = records.iter().map(|r| r.cost.market_impact_eur).sum();
        let total_commission: f64 = records.iter().map(|r| r.cost.commission_eur).sum();
        let total_fees: f64 = records.iter().map(|r| r.cost.fees_eur).sum();
        let total_value: f64 = records.iter().map(|r| r.executed_value_eur()).sum();

        Some(ExecutionCost::new(
            total_spread / records.len() as f64,
            total_impact / records.len() as f64,
            total_commission / records.len() as f64,
            total_fees / records.len() as f64,
            total_value / records.len() as f64,
        ))
    }

    /// Identify venues with highest/lowest costs for reporting
    pub fn venue_cost_summary(&self) -> Vec<(Uuid, ExecutionCost)> {
        let mut venue_costs: std::collections::HashMap<Uuid, Vec<ExecutionCost>> =
            std::collections::HashMap::new();

        for record in self.records.iter() {
            venue_costs
                .entry(record.venue_id)
                .or_insert_with(Vec::new)
                .push(record.cost);
        }

        let mut result = Vec::new();
        for (venue_id, costs) in venue_costs {
            if !costs.is_empty() {
                let avg_spread: f64 = costs.iter().map(|c| c.spread_cost_eur).sum::<f64>()
                    / costs.len() as f64;
                let avg_impact: f64 = costs.iter().map(|c| c.market_impact_eur).sum::<f64>()
                    / costs.len() as f64;
                let avg_commission: f64 =
                    costs.iter().map(|c| c.commission_eur).sum::<f64>() / costs.len() as f64;
                let avg_fees: f64 = costs.iter().map(|c| c.fees_eur).sum::<f64>()
                    / costs.len() as f64;

                let avg_cost = ExecutionCost::new(
                    avg_spread,
                    avg_impact,
                    avg_commission,
                    avg_fees,
                    costs.iter().map(|c| c.total_cost_eur).sum::<f64>() / costs.len() as f64,
                );

                result.push((venue_id, avg_cost));
            }
        }

        result.sort_by(|a, b| a.1.total_cost_eur.partial_cmp(&b.1.total_cost_eur).unwrap());
        result
    }

    pub fn count_records(&self) -> usize {
        self.records.len()
    }
}

impl Default for CostAnalyzer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_execution_cost_creation() {
        let cost = ExecutionCost::new(10.0, 5.0, 2.0, 1.0, 10000.0);
        assert_eq!(cost.total_cost_eur, 18.0);
        assert!((cost.cost_as_percentage - 0.18).abs() < 0.01);
    }

    #[test]
    fn test_execution_cost_in_bps() {
        let cost = ExecutionCost::new(10.0, 5.0, 2.0, 1.0, 10000.0);
        let bps = cost.cost_in_bps(10000.0);
        assert!((bps - 18.0).abs() < 0.1);
    }

    #[test]
    fn test_execution_cost_retail_acceptable() {
        let cost = ExecutionCost::new(5.0, 2.0, 1.0, 0.5, 10000.0);
        assert!(cost.is_acceptable_for_retail());
    }

    #[test]
    fn test_execution_cost_retail_not_acceptable() {
        let cost = ExecutionCost::new(100.0, 50.0, 25.0, 10.0, 10000.0);
        assert!(!cost.is_acceptable_for_retail());
    }

    #[test]
    fn test_cost_analysis_record_creation() {
        let order_id = Uuid::new_v4();
        let venue_id = Uuid::new_v4();
        let cost = ExecutionCost::new(5.0, 2.0, 1.0, 0.5, 10000.0);

        let record = CostAnalysisRecord::new(order_id, venue_id, cost, 100, 100.50);

        assert_eq!(record.order_id, order_id);
        assert_eq!(record.venue_id, venue_id);
        assert_eq!(record.executed_value_eur(), 10050.0);
    }

    #[test]
    fn test_cost_analyzer_add_record() {
        let analyzer = CostAnalyzer::new();
        let order_id = Uuid::new_v4();
        let venue_id = Uuid::new_v4();
        let cost = ExecutionCost::new(5.0, 2.0, 1.0, 0.5, 10000.0);

        let record = CostAnalysisRecord::new(order_id, venue_id, cost, 100, 100.50);
        let record_id = record.id;

        analyzer.add_record(record);
        assert_eq!(analyzer.count_records(), 1);
        assert!(analyzer.get_record(record_id).is_some());
    }

    #[test]
    fn test_cost_analyzer_get_records_for_order() {
        let analyzer = CostAnalyzer::new();
        let order_id = Uuid::new_v4();
        let venue1 = Uuid::new_v4();
        let venue2 = Uuid::new_v4();

        let cost1 = ExecutionCost::new(5.0, 2.0, 1.0, 0.5, 5000.0);
        let cost2 = ExecutionCost::new(3.0, 1.0, 0.5, 0.3, 5000.0);

        analyzer.add_record(CostAnalysisRecord::new(order_id, venue1, cost1, 50, 100.50));
        analyzer.add_record(CostAnalysisRecord::new(order_id, venue2, cost2, 50, 100.50));

        let records = analyzer.get_records_for_order(order_id);
        assert_eq!(records.len(), 2);
    }

    #[test]
    fn test_cost_analyzer_average_cost() {
        let analyzer = CostAnalyzer::new();
        let order_id = Uuid::new_v4();
        let venue_id = Uuid::new_v4();

        let cost1 = ExecutionCost::new(5.0, 2.0, 1.0, 0.5, 5000.0);
        let cost2 = ExecutionCost::new(7.0, 3.0, 1.5, 0.7, 5000.0);

        analyzer.add_record(CostAnalysisRecord::new(order_id, venue_id, cost1, 50, 100.0));
        analyzer.add_record(CostAnalysisRecord::new(order_id, venue_id, cost2, 50, 100.0));

        let avg = analyzer.average_cost_for_order(order_id);
        assert!(avg.is_some());
    }

    #[test]
    fn test_cost_analyzer_venue_cost_summary() {
        let analyzer = CostAnalyzer::new();
        let order_id = Uuid::new_v4();
        let venue1 = Uuid::new_v4();
        let venue2 = Uuid::new_v4();

        let cost1 = ExecutionCost::new(5.0, 2.0, 1.0, 0.5, 5000.0);
        let cost2 = ExecutionCost::new(3.0, 1.0, 0.5, 0.3, 5000.0);

        analyzer.add_record(CostAnalysisRecord::new(order_id, venue1, cost1, 50, 100.0));
        analyzer.add_record(CostAnalysisRecord::new(order_id, venue2, cost2, 50, 100.0));

        let summary = analyzer.venue_cost_summary();
        assert_eq!(summary.len(), 2);
        // venue2 should be first (lower cost)
        assert_eq!(summary[0].0, venue2);
    }
}
