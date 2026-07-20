#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum EarCategory {
    Cat0, Cat1, Cat2, Cat3, Cat4, Cat5, Cat6, Cat7, Cat8, Cat9,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum EarLicenseException {
    ENC, TSR, LVS,
}

#[derive(Debug, Clone)]
pub struct EarClassification {
    pub eccn: String,
    pub license_exception: Option<EarLicenseException>,
}
