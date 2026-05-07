pub mod budget;
pub mod tools;
pub mod content;

use crate::context::InspectionContext;
use crate::types::Violation;

pub trait FirewallChecker: Send + Sync {
    fn name(&self) -> &str;
    fn check(&self, context: &InspectionContext) -> Vec<Violation>;
}
