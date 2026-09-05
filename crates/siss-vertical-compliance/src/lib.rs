//! SovereignNexus Vertical Compliance Framework
//! 
//! Provides compliance frameworks, ReBAC roles, and pilot test harnesses
//! for Defense (FedRAMP), Healthcare (HIPAA), and Finance (MiFID II) verticals.

pub mod defense {
    pub mod policy_templates;
}

pub mod healthcare {
    pub mod policy_templates;
}

pub mod finance {
    pub mod policy_templates;
}

pub mod shared {
    pub mod contracts;
}
