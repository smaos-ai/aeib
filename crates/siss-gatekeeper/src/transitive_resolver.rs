/// Phase 11: Transitive Trust Resolution
/// Cross-sovereign delegation context and depth tracking
use uuid::Uuid;

/// Context for a federated operation with transitive delegation support.
#[derive(Debug, Clone)]
pub struct TransitiveFederatedContext {
    pub source_sovereign_id: Uuid,
    pub admitted_tier: u32,
    pub is_cross_sovereign: bool,
    pub grant_id: Option<Uuid>,
    pub transitivity_depth: Option<i16>,
    pub grant_ceiling_tier: Option<u32>,
}

impl TransitiveFederatedContext {
    /// Create a new transitive federated context.
    pub fn new(source_sovereign_id: Uuid, admitted_tier: u32) -> Self {
        Self {
            source_sovereign_id,
            admitted_tier,
            is_cross_sovereign: true,
            grant_id: None,
            transitivity_depth: None,
            grant_ceiling_tier: None,
        }
    }

    /// Set delegation grant information.
    pub fn with_grant(
        mut self,
        grant_id: Uuid,
        transitivity_depth: i16,
        grant_ceiling_tier: u32,
    ) -> Self {
        self.grant_id = Some(grant_id);
        self.transitivity_depth = Some(transitivity_depth);
        self.grant_ceiling_tier = Some(grant_ceiling_tier);
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transitive_federated_context_new() {
        let sovereign_id = Uuid::new_v4();
        let ctx = TransitiveFederatedContext::new(sovereign_id, 50);

        assert_eq!(ctx.source_sovereign_id, sovereign_id);
        assert_eq!(ctx.admitted_tier, 50);
        assert!(ctx.is_cross_sovereign);
        assert!(ctx.grant_id.is_none());
        assert!(ctx.transitivity_depth.is_none());
        assert!(ctx.grant_ceiling_tier.is_none());
    }

    #[test]
    fn test_transitive_federated_context_with_grant() {
        let sovereign_id = Uuid::new_v4();
        let grant_id = Uuid::new_v4();
        let ctx = TransitiveFederatedContext::new(sovereign_id, 50).with_grant(grant_id, 2, 40);

        assert_eq!(ctx.grant_id, Some(grant_id));
        assert_eq!(ctx.transitivity_depth, Some(2));
        assert_eq!(ctx.grant_ceiling_tier, Some(40));
    }
}
