/// Phase 63: UCP Checkout Router — transport-agnostic cart payload construction.
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CheckoutTransport {
    Rest,
    Mcp,
    A2a,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CartItem {
    pub item_id: Uuid,
    pub name: String,
    pub unit_price: i64,
    pub quantity: u32,
}

#[derive(Debug, Clone)]
pub struct CartRequest {
    pub cart_id: Uuid,
    pub mandate_id: Uuid,
    pub items: Vec<CartItem>,
    pub transport: CheckoutTransport,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CheckoutPayload {
    pub cart_id: Uuid,
    pub mandate_id: Uuid,
    pub items: Vec<CartItem>,
    pub total: i64,
    pub item_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CheckoutError {
    EmptyCart,
}

pub struct UcpCheckoutRouter;

impl UcpCheckoutRouter {
    pub fn route(request: CartRequest) -> Result<CheckoutPayload, CheckoutError> {
        if request.items.is_empty() {
            return Err(CheckoutError::EmptyCart);
        }

        let item_count = request.items.len();
        let total: i64 = request
            .items
            .iter()
            .map(|item| item.unit_price * (item.quantity as i64))
            .sum();

        Ok(CheckoutPayload {
            cart_id: request.cart_id,
            mandate_id: request.mandate_id,
            items: request.items,
            total,
            item_count,
        })
    }
}
