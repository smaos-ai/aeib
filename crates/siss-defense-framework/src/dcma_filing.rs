use crate::{CountryDenyList, EarLicenseException};

#[derive(Debug, Clone)]
pub struct DcmaFilingPackage {
    pub destination: String,
    pub eccn: String,
    pub license_exception: Option<EarLicenseException>,
    pub itar_controlled: bool,
    pub filing_ready: bool,
}

const ECCN_5D002_C1: &str = "ECCN 5D002.c.1";
const COUNTRY_BLOCKED: &str = "COUNTRY_BLOCKED";

pub fn generate_dcma_package(destination: &str) -> Result<DcmaFilingPackage, String> {
    let country_list = CountryDenyList::seed_ofac();

    if country_list.is_denied(destination) {
        return Err(COUNTRY_BLOCKED.to_string());
    }

    let itar_controlled = check_itar_control(destination);
    if itar_controlled {
        return Err("ITAR_CONTROLLED".to_string());
    }

    let ear_check = check_ear_license(destination);
    let license_exception = if destination == "IL" {
        Some(EarLicenseException::ENC)
    } else {
        None
    };

    Ok(DcmaFilingPackage {
        destination: destination.to_string(),
        eccn: ECCN_5D002_C1.to_string(),
        license_exception,
        itar_controlled: false,
        filing_ready: !ear_check.is_err(),
    })
}

fn check_itar_control(destination: &str) -> bool {
    matches!(destination, "KP" | "SY" | "CU")
}

fn check_ear_license(destination: &str) -> Result<(), String> {
    match destination {
        "IL" | "DE" => Ok(()),
        "IR" => Err("COUNTRY_BLOCKED".to_string()),
        _ => Ok(()),
    }
}
