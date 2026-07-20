use crate::hooks::HookResult;
/// Phase 63: AP2 Mandate Gate — role-separated payment authorization.
use siss_gatekeeper::signer::{Signer, SigningError};
use siss_gatekeeper::tokens::IntentMandate;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct PaymentMandate {
    pub mandate_id: Uuid,
    pub cart_id: Uuid,
    pub total: i64,
    pub intent_mandate_id: Uuid,
    pub signature: Option<Vec<u8>>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MandateError {
    SpendingLimitExceeded { total: i64, limit: i64 },
    MandateNotSigned,
    SigningFailed(String),
}

pub struct Ap2MandateGate<S: Signer> {
    pub signer: S,
    pub intent_mandate: IntentMandate,
}

impl<S: Signer> Ap2MandateGate<S> {
    pub fn issue_mandate(&self, cart_id: Uuid, total: i64) -> (PaymentMandate, HookResult) {
        let remaining = self.intent_mandate.budget_remaining();

        if total <= remaining {
            let payload = format!("mandate:{}:{}", cart_id, total);
            match self.signer.sign(payload.as_bytes()) {
                Ok(sig) => {
                    let mandate = PaymentMandate {
                        mandate_id: Uuid::new_v4(),
                        cart_id,
                        total,
                        intent_mandate_id: self.intent_mandate.id,
                        signature: Some(sig),
                    };
                    (mandate, HookResult::Continue)
                }
                Err(e) => {
                    let mandate = PaymentMandate {
                        mandate_id: Uuid::new_v4(),
                        cart_id,
                        total,
                        intent_mandate_id: self.intent_mandate.id,
                        signature: None,
                    };
                    (
                        mandate,
                        HookResult::Halt {
                            reason: format!("signing_failed:{}", e),
                        },
                    )
                }
            }
        } else {
            let mandate = PaymentMandate {
                mandate_id: Uuid::new_v4(),
                cart_id,
                total,
                intent_mandate_id: self.intent_mandate.id,
                signature: None,
            };
            (
                mandate,
                HookResult::Halt {
                    reason: format!(
                        "spending_limit_exceeded:total={}:limit={}",
                        total, remaining
                    ),
                },
            )
        }
    }

    pub fn approve_with_signature(
        &self,
        mut mandate: PaymentMandate,
        human_sig: Vec<u8>,
    ) -> PaymentMandate {
        mandate.signature = Some(human_sig);
        mandate
    }

    pub fn authorize_execution(&self, mandate: &PaymentMandate) -> HookResult {
        if mandate.signature.is_some() {
            HookResult::Continue
        } else {
            HookResult::Halt {
                reason: "unsigned_mandate:execution_blocked".to_string(),
            }
        }
    }
}
