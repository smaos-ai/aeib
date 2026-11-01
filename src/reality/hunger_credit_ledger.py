# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
src/reality/hunger_credit_ledger.py — Thermodynamic Hunger Protocol & Bankruptcy Latch.

Solves the "Unbounded Agent Flailing" failure mode:
When an autonomous agent encounters an unfamiliar error, it frequently enters an infinite
mutation loop, repeatedly modifying files, running tests, and burning tens of thousands of tokens
without making forward progress.

The HungerCreditLedger assigns the agent a thermodynamic credit balance (default 1,000 units):
- Deduction penalties:
  - Mutation failure: -100 units
  - Blind identical retry: -50 units
  - Scope expansion (touching unowned files): -200 units
  - Redundant tool execution: -20 units
- Rewards:
  - Mutation test kill: +50 units
- When balance <= 0, the ledger latches `HALT_BANKRUPT`, issues an Ed25519-signed
  `BankruptcyDeathCertificate`, and locks all action dispatch until cleared by an operator.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from src.jcs_canonicalizer import encode_jcs

DEFAULT_INITIAL_CREDITS: int = 1000
PENALTY_MUTATION_FAILURE: int = 100
PENALTY_BLIND_RETRY: int = 50
PENALTY_SCOPE_EXPANSION: int = 200
PENALTY_REDUNDANT_TOOL: int = 20
REWARD_MUTATION_KILLED: int = 50


@dataclass(frozen=True)
class CreditTransaction:
    tx_id: str
    agent_id: str
    delta: int
    resulting_balance: int
    reason: str
    timestamp_ns: int


@dataclass(frozen=True)
class BankruptcyDeathCertificate:
    certificate_id: str
    agent_id: str
    final_balance: int
    trigger_reason: str
    total_transactions: int
    operator_pubkey_hex: str
    signature_hex: str
    certificate_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "agent_id": self.agent_id,
            "final_balance": self.final_balance,
            "trigger_reason": self.trigger_reason,
            "total_transactions": self.total_transactions,
            "operator_pubkey_hex": self.operator_pubkey_hex,
            "signature_hex": self.signature_hex,
            "certificate_caid": self.certificate_caid,
        }


class HungerCreditLedger:
    """
    Thermodynamic energy and credit governor for autonomous agent execution.
    """

    def __init__(
        self,
        agent_id: str,
        initial_credits: int = DEFAULT_INITIAL_CREDITS,
    ) -> None:
        self.agent_id = agent_id
        self.balance = initial_credits
        self.is_bankrupt = (self.balance <= 0)
        self.history: List[CreditTransaction] = []
        self._tx_counter = 0

    def deduct(
        self,
        amount: int,
        reason: str,
        now_ns: Optional[int] = None,
    ) -> Tuple[bool, int, str]:
        """
        Deducts credit points. Returns (can_continue, current_balance, status_code).
        If balance drops <= 0, latches is_bankrupt = True.
        """
        if self.is_bankrupt:
            return False, self.balance, "HALT_BANKRUPT_LATCHED"

        self._tx_counter += 1
        ts = now_ns if now_ns is not None else time.time_ns()
        self.balance -= amount

        tx = CreditTransaction(
            tx_id=f"TX-{self._tx_counter:05d}",
            agent_id=self.agent_id,
            delta=-amount,
            resulting_balance=self.balance,
            reason=reason,
            timestamp_ns=ts,
        )
        self.history.append(tx)

        if self.balance <= 0:
            self.is_bankrupt = True
            return False, self.balance, "HALT_BANKRUPT_CREDITS_EXHAUSTED"

        return True, self.balance, "ALLOW_CREDIT_REMAINING"

    def reward(
        self,
        amount: int,
        reason: str,
        now_ns: Optional[int] = None,
    ) -> Tuple[bool, int, str]:
        """
        Awards credits for verified milestones. Cannot unlatch bankruptcy automatically.
        """
        if self.is_bankrupt:
            return False, self.balance, "HALT_BANKRUPT_LATCHED"

        self._tx_counter += 1
        ts = now_ns if now_ns is not None else time.time_ns()
        self.balance += amount

        tx = CreditTransaction(
            tx_id=f"TX-{self._tx_counter:05d}",
            agent_id=self.agent_id,
            delta=amount,
            resulting_balance=self.balance,
            reason=reason,
            timestamp_ns=ts,
        )
        self.history.append(tx)
        return True, self.balance, "CREDIT_REWARDED"

    def issue_death_certificate(
        self,
        operator_private_key: Ed25519PrivateKey,
        certificate_id: str = "DEATH-CERT-001",
    ) -> BankruptcyDeathCertificate:
        """
        Issues an Ed25519 signed BankruptcyDeathCertificate.
        """
        if not self.is_bankrupt:
            raise RuntimeError("Cannot issue death certificate: Agent is not bankrupt")

        last_reason = self.history[-1].reason if self.history else "CREDIT_EXHAUSTED"
        pubkey_hex = operator_private_key.public_key().public_bytes_raw().hex()

        body = {
            "certificate_id": certificate_id,
            "agent_id": self.agent_id,
            "final_balance": self.balance,
            "trigger_reason": last_reason,
            "total_transactions": len(self.history),
            "operator_pubkey_hex": pubkey_hex,
        }
        canonical_bytes = encode_jcs(body)
        sig = operator_private_key.sign(canonical_bytes).hex()
        cert_caid = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()

        return BankruptcyDeathCertificate(
            certificate_id=certificate_id,
            agent_id=self.agent_id,
            final_balance=self.balance,
            trigger_reason=last_reason,
            total_transactions=len(self.history),
            operator_pubkey_hex=pubkey_hex,
            signature_hex=sig,
            certificate_caid=cert_caid,
        )

    def clear_bankruptcy(self, restore_credits: int = DEFAULT_INITIAL_CREDITS) -> None:
        """Operator clearance latch resetting bankruptcy state."""
        self.balance = restore_credits
        self.is_bankrupt = False
        self._tx_counter += 1
        self.history.append(
            CreditTransaction(
                tx_id=f"TX-{self._tx_counter:05d}",
                agent_id=self.agent_id,
                delta=restore_credits,
                resulting_balance=self.balance,
                reason="OPERATOR_MANUAL_CLEARANCE",
                timestamp_ns=time.time_ns(),
            )
        )
