use crate::types::{LicenseError, Sku};

pub struct LicenseEnforcer;

impl LicenseEnforcer {
    pub fn check_agent_limit(&self, sku: &Sku, current_count: u32) -> Result<(), LicenseError> {
        if let Some(limit) = sku.agent_limit()
            && current_count >= limit {
                return Err(LicenseError::AgentLimitExceeded);
            }
        Ok(())
    }

    pub fn check_api_quota(&self, sku: &Sku, used_today: u64) -> Result<(), LicenseError> {
        if let Some(limit) = sku.daily_api_limit()
            && used_today >= limit {
                return Err(LicenseError::QuotaExceeded);
            }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_starter_sku_5_agents_allowed() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Starter, 4);
        assert!(result.is_ok());
    }

    #[test]
    fn test_starter_sku_5_agents_exact() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Starter, 5);
        assert!(matches!(result, Err(LicenseError::AgentLimitExceeded)));
    }

    #[test]
    fn test_starter_sku_6_agents_blocked() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Starter, 6);
        assert!(matches!(result, Err(LicenseError::AgentLimitExceeded)));
    }

    #[test]
    fn test_pro_sku_50_agents_allowed() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Pro, 49);
        assert!(result.is_ok());
    }

    #[test]
    fn test_pro_sku_50_agents_exact() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Pro, 50);
        assert!(matches!(result, Err(LicenseError::AgentLimitExceeded)));
    }

    #[test]
    fn test_pro_sku_51_agents_blocked() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Pro, 51);
        assert!(matches!(result, Err(LicenseError::AgentLimitExceeded)));
    }

    #[test]
    fn test_enterprise_sku_unlimited_agents() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Enterprise, 1000);
        assert!(result.is_ok());
    }

    #[test]
    fn test_enterprise_sku_unlimited_agents_high() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Enterprise, u32::MAX - 1);
        assert!(result.is_ok());
    }

    #[test]
    fn test_starter_api_quota_1k_per_day() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_api_quota(&Sku::Starter, 999);
        assert!(result.is_ok());
    }

    #[test]
    fn test_starter_api_quota_1k_exact() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_api_quota(&Sku::Starter, 1_000);
        assert!(matches!(result, Err(LicenseError::QuotaExceeded)));
    }

    #[test]
    fn test_starter_api_quota_1001_blocked() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_api_quota(&Sku::Starter, 1_001);
        assert!(matches!(result, Err(LicenseError::QuotaExceeded)));
    }

    #[test]
    fn test_pro_api_quota_100k_per_day() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_api_quota(&Sku::Pro, 99_999);
        assert!(result.is_ok());
    }

    #[test]
    fn test_pro_api_quota_100k_exact() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_api_quota(&Sku::Pro, 100_000);
        assert!(matches!(result, Err(LicenseError::QuotaExceeded)));
    }

    #[test]
    fn test_pro_api_quota_100001_blocked() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_api_quota(&Sku::Pro, 100_001);
        assert!(matches!(result, Err(LicenseError::QuotaExceeded)));
    }

    #[test]
    fn test_enterprise_api_quota_unlimited() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_api_quota(&Sku::Enterprise, u64::MAX - 1);
        assert!(result.is_ok());
    }

    #[test]
    fn test_monthly_price_starter() {
        assert_eq!(Sku::Starter.monthly_price_cents(), Some(2999));
    }

    #[test]
    fn test_monthly_price_pro() {
        assert_eq!(Sku::Pro.monthly_price_cents(), Some(9999));
    }

    #[test]
    fn test_monthly_price_enterprise_custom() {
        assert_eq!(Sku::Enterprise.monthly_price_cents(), None);
    }

    #[test]
    fn test_agent_limit_transitions_starter_to_pro() {
        let enforcer = LicenseEnforcer;
        let result = enforcer.check_agent_limit(&Sku::Starter, 5);
        assert!(result.is_err());

        let result = enforcer.check_agent_limit(&Sku::Pro, 5);
        assert!(result.is_ok());
    }

    #[test]
    fn test_quota_check_zero_used() {
        let enforcer = LicenseEnforcer;
        assert!(enforcer.check_api_quota(&Sku::Starter, 0).is_ok());
        assert!(enforcer.check_api_quota(&Sku::Pro, 0).is_ok());
        assert!(enforcer.check_api_quota(&Sku::Enterprise, 0).is_ok());
    }
}
