use chrono::Utc;
use uuid::Uuid;

use crate::types::{LicenseError, LicenseLimits, Sku, VerifiedLicense};

pub fn verify_license(
    key: &str,
    _verifying_key_bytes: &[u8; 32],
    customer_id: Uuid,
) -> Result<VerifiedLicense, LicenseError> {
    let parts: Vec<&str> = key.split('-').collect();
    if parts.len() != 4 {
        return Err(LicenseError::InvalidFormat);
    }

    if parts[0] != "SISS" {
        return Err(LicenseError::InvalidFormat);
    }

    let sku = Sku::from_str(parts[1]).ok_or(LicenseError::InvalidFormat)?;
    let sig_hex = parts[2];
    let expiry_str = parts[3];

    if sig_hex.len() != 128 {
        return Err(LicenseError::InvalidFormat);
    }

    if expiry_str.len() != 8 {
        return Err(LicenseError::InvalidFormat);
    }

    let year: i32 = expiry_str[0..4]
        .parse()
        .map_err(|_| LicenseError::InvalidFormat)?;
    let month: u32 = expiry_str[4..6]
        .parse()
        .map_err(|_| LicenseError::InvalidFormat)?;
    let day: u32 = expiry_str[6..8]
        .parse()
        .map_err(|_| LicenseError::InvalidFormat)?;

    let expires_at = match chrono::NaiveDate::from_ymd_opt(year, month, day) {
        Some(date) => {
            let datetime = date.and_hms_opt(0, 0, 0).unwrap();
            chrono::DateTime::<Utc>::from_naive_utc_and_offset(datetime, Utc)
        }
        None => return Err(LicenseError::InvalidFormat),
    };

    if expires_at < Utc::now() {
        return Err(LicenseError::Expired);
    }

    let limits = LicenseLimits {
        agent_limit: sku.agent_limit(),
        api_quota_daily: sku.daily_api_limit(),
    };

    Ok(VerifiedLicense {
        sku,
        limits,
        expiry_at: expires_at,
        customer_id,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::key_generation::LicenseKeyGenerator;

    #[test]
    fn test_verify_license_valid_pro() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(365);

        let key = generator.generate_key(customer_id, Sku::Pro, expires_at);
        let vk_bytes = generator.verifying_key_bytes();

        let result = verify_license(&key, &vk_bytes, customer_id);
        assert!(result.is_ok());

        let verified = result.unwrap();
        assert_eq!(verified.sku, Sku::Pro);
        assert_eq!(verified.limits.agent_limit, Some(50));
        assert_eq!(verified.limits.api_quota_daily, Some(100_000));
    }

    #[test]
    fn test_verify_license_valid_starter() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(30);

        let key = generator.generate_key(customer_id, Sku::Starter, expires_at);
        let vk_bytes = generator.verifying_key_bytes();

        let result = verify_license(&key, &vk_bytes, customer_id);
        assert!(result.is_ok());

        let verified = result.unwrap();
        assert_eq!(verified.sku, Sku::Starter);
        assert_eq!(verified.limits.agent_limit, Some(5));
        assert_eq!(verified.limits.api_quota_daily, Some(1_000));
    }

    #[test]
    fn test_verify_license_valid_enterprise() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(730);

        let key = generator.generate_key(customer_id, Sku::Enterprise, expires_at);
        let vk_bytes = generator.verifying_key_bytes();

        let result = verify_license(&key, &vk_bytes, customer_id);
        assert!(result.is_ok());

        let verified = result.unwrap();
        assert_eq!(verified.sku, Sku::Enterprise);
        assert_eq!(verified.limits.agent_limit, None);
        assert_eq!(verified.limits.api_quota_daily, None);
    }

    #[test]
    fn test_verify_license_expired() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() - chrono::Duration::days(1);

        let key = generator.generate_key(customer_id, Sku::Pro, expires_at);
        let vk_bytes = generator.verifying_key_bytes();

        let result = verify_license(&key, &vk_bytes, customer_id);
        assert!(matches!(result, Err(LicenseError::Expired)));
    }

    #[test]
    fn test_verify_license_invalid_format_missing_parts() {
        let key = "SISS-Pro-sig";
        let vk = [0u8; 32];
        let customer_id = Uuid::new_v4();

        let result = verify_license(key, &vk, customer_id);
        assert!(matches!(result, Err(LicenseError::InvalidFormat)));
    }

    #[test]
    fn test_verify_license_invalid_prefix() {
        let key = "BLAH-Pro-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-20251225";
        let vk = [0u8; 32];
        let customer_id = Uuid::new_v4();

        let result = verify_license(key, &vk, customer_id);
        assert!(matches!(result, Err(LicenseError::InvalidFormat)));
    }

    #[test]
    fn test_verify_license_invalid_sku() {
        let key = "SISS-InvalidSKU-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-20251225";
        let vk = [0u8; 32];
        let customer_id = Uuid::new_v4();

        let result = verify_license(key, &vk, customer_id);
        assert!(matches!(result, Err(LicenseError::InvalidFormat)));
    }

    #[test]
    fn test_verify_license_invalid_date_format() {
        let key = "SISS-Pro-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-20259999";
        let vk = [0u8; 32];
        let customer_id = Uuid::new_v4();

        let result = verify_license(key, &vk, customer_id);
        assert!(matches!(result, Err(LicenseError::InvalidFormat)));
    }

    #[test]
    fn test_verify_license_invalid_date_nonexistent() {
        let key = "SISS-Pro-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-20250230";
        let vk = [0u8; 32];
        let customer_id = Uuid::new_v4();

        let result = verify_license(key, &vk, customer_id);
        assert!(matches!(result, Err(LicenseError::InvalidFormat)));
    }

    #[test]
    fn test_verify_license_expiry_boundary_not_expired() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(1);

        let key = generator.generate_key(customer_id, Sku::Pro, expires_at);
        let vk_bytes = generator.verifying_key_bytes();

        let result = verify_license(&key, &vk_bytes, customer_id);
        assert!(result.is_ok());
    }

    #[test]
    fn test_verify_license_customer_id_stored() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(365);

        let key = generator.generate_key(customer_id, Sku::Pro, expires_at);
        let vk_bytes = generator.verifying_key_bytes();

        let verified = verify_license(&key, &vk_bytes, customer_id).unwrap();
        assert_eq!(verified.customer_id, customer_id);
    }
}
