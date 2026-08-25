use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Order status
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum OrderStatus {
    Pending,
    Accepted,
    PartiallyFilled,
    Filled,
    Cancelled,
    Rejected,
}

impl OrderStatus {
    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            OrderStatus::Filled | OrderStatus::Cancelled | OrderStatus::Rejected
        )
    }
}

/// MiFID II Order with best execution tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Order {
    pub id: Uuid,
    pub client_id: Uuid,
    pub instrument_id: String,      // ISIN or similar
    pub side: String,                 // "BUY" or "SELL"
    pub quantity: u64,
    pub limit_price_eur: Option<f64>,
    pub created_at: DateTime<Utc>,
    pub status: OrderStatus,
    pub executed_quantity: u64,
    pub executed_price_avg_eur: Option<f64>,
    pub executed_at: Option<DateTime<Utc>>,
    pub client_category: ClientCategory,
}

/// Client classification for best execution rules
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum ClientCategory {
    Retail,
    Professional,
    Eligible,
}

impl Order {
    pub fn new(
        client_id: Uuid,
        instrument_id: String,
        side: String,
        quantity: u64,
        client_category: ClientCategory,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            client_id,
            instrument_id,
            side,
            quantity,
            limit_price_eur: None,
            created_at: Utc::now(),
            status: OrderStatus::Pending,
            executed_quantity: 0,
            executed_price_avg_eur: None,
            executed_at: None,
            client_category,
        }
    }

    pub fn with_limit_price(mut self, price: f64) -> Self {
        self.limit_price_eur = Some(price);
        self
    }

    /// Fill order with execution price
    pub fn fill(&mut self, executed_quantity: u64, executed_price: f64) -> Result<(), String> {
        if self.status.is_terminal() {
            return Err(format!(
                "Order {:?} is in terminal status {:?}",
                self.id, self.status
            ));
        }

        if executed_quantity == 0 {
            return Err("Executed quantity must be > 0".to_string());
        }

        if executed_quantity > self.quantity - self.executed_quantity {
            return Err("Executed quantity exceeds remaining order quantity".to_string());
        }

        // Update average execution price
        let total_executed_value =
            (self.executed_quantity as f64 * self.executed_price_avg_eur.unwrap_or(executed_price))
                + (executed_quantity as f64 * executed_price);
        let new_executed_quantity = self.executed_quantity + executed_quantity;

        self.executed_price_avg_eur = Some(total_executed_value / new_executed_quantity as f64);
        self.executed_quantity = new_executed_quantity;
        self.executed_at = Some(Utc::now());

        if self.executed_quantity == self.quantity {
            self.status = OrderStatus::Filled;
        } else {
            self.status = OrderStatus::PartiallyFilled;
        }

        Ok(())
    }

    /// Get best execution applicability
    pub fn requires_best_execution(&self) -> bool {
        // Retail and professional clients require best execution
        // Eligible counterparties may opt-out
        !matches!(self.client_category, ClientCategory::Eligible)
    }

    /// Check if order meets execution requirements
    pub fn is_executable(&self) -> bool {
        !self.status.is_terminal() && self.quantity > 0
    }
}

/// Order manager with best execution tracking
pub struct OrderManager {
    orders: dashmap::DashMap<Uuid, Order>,
}

impl OrderManager {
    pub fn new() -> Self {
        Self {
            orders: dashmap::DashMap::new(),
        }
    }

    pub fn add_order(&self, order: Order) -> Result<Uuid, String> {
        if !order.is_executable() {
            return Err("Order is not executable".to_string());
        }
        let order_id = order.id;
        self.orders.insert(order_id, order);
        Ok(order_id)
    }

    pub fn get_order(&self, order_id: Uuid) -> Option<Order> {
        self.orders.get(&order_id).map(|o| o.clone())
    }

    pub fn get_all_orders(&self) -> Vec<Order> {
        self.orders.iter().map(|o| o.value().clone()).collect()
    }

    pub fn get_pending_orders(&self) -> Vec<Order> {
        self.orders
            .iter()
            .filter(|o| o.status == OrderStatus::Pending)
            .map(|o| o.clone())
            .collect()
    }

    pub fn update_order(&self, order_id: Uuid, order: Order) -> Result<(), String> {
        self.orders
            .alter(&order_id, |_, _| order);
        Ok(())
    }

    pub fn count_orders(&self) -> usize {
        self.orders.len()
    }
}

impl Default for OrderManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_order_creation() {
        let client_id = Uuid::new_v4();
        let order = Order::new(
            client_id,
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Retail,
        );

        assert_eq!(order.status, OrderStatus::Pending);
        assert_eq!(order.executed_quantity, 0);
        assert!(order.is_executable());
        assert!(order.requires_best_execution());
    }

    #[test]
    fn test_order_with_limit_price() {
        let order = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Retail,
        )
        .with_limit_price(100.50);

        assert_eq!(order.limit_price_eur, Some(100.50));
    }

    #[test]
    fn test_order_fill() {
        let mut order = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Retail,
        );

        let result = order.fill(500, 100.25);
        assert!(result.is_ok());
        assert_eq!(order.executed_quantity, 500);
        assert_eq!(order.status, OrderStatus::PartiallyFilled);
        assert_eq!(order.executed_price_avg_eur, Some(100.25));
    }

    #[test]
    fn test_order_fill_complete() {
        let mut order = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Retail,
        );

        let _ = order.fill(500, 100.25);
        let result = order.fill(500, 100.30);
        assert!(result.is_ok());
        assert_eq!(order.executed_quantity, 1000);
        assert_eq!(order.status, OrderStatus::Filled);
        // Average: (500*100.25 + 500*100.30) / 1000 = 100.275
        assert_eq!(order.executed_price_avg_eur, Some(100.275));
    }

    #[test]
    fn test_order_fill_exceeds_quantity() {
        let mut order = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Retail,
        );

        let result = order.fill(1500, 100.25);
        assert!(result.is_err());
        assert_eq!(order.executed_quantity, 0);
    }

    #[test]
    fn test_order_manager_add_order() {
        let manager = OrderManager::new();
        let order = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Retail,
        );

        let order_id = order.id;
        let result = manager.add_order(order);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), order_id);
        assert_eq!(manager.count_orders(), 1);
    }

    #[test]
    fn test_order_manager_get_order() {
        let manager = OrderManager::new();
        let order = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Professional,
        );

        let order_id = order.id;
        let _ = manager.add_order(order);
        let retrieved = manager.get_order(order_id);

        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().status, OrderStatus::Pending);
    }

    #[test]
    fn test_order_manager_pending_orders() {
        let manager = OrderManager::new();
        let mut order1 = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Retail,
        );

        let order2 = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y984".to_string(),
            "SELL".to_string(),
            500,
            ClientCategory::Professional,
        );

        let _ = manager.add_order(order1.clone());
        order1.status = OrderStatus::Filled;
        let _ = manager.add_order(order2);

        let pending = manager.get_pending_orders();
        assert_eq!(pending.len(), 1);
    }

    #[test]
    fn test_eligible_counterparty_no_best_execution() {
        let order = Order::new(
            Uuid::new_v4(),
            "IE00B4L5Y983".to_string(),
            "BUY".to_string(),
            1000,
            ClientCategory::Eligible,
        );

        assert!(!order.requires_best_execution());
    }
}
