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

"""Moat 6: Hardware-Rooted Attestation Scaffold (IETF RATS / TPM 2.0 / SEV-SNP)

IMPORTANT HONESTY BOUNDARY:
- This module is a structural envelope scaffold. It does NOT verify X.509/AMD VCEK,
  Intel PCS, AWS Nitro COSE_Sign1, or TPM 2.0 AIK cryptographic signatures.
- By default (`allow_simulation=False`), `HardwareAttestationVerifier.verify`
  returns `is_valid=False` with `status=NOT_EXECUTED` so a 32-character dummy string
  is never accepted as a hardware attestation quote.
"""

import base64
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from src.capability_status import NOT_EXECUTED, SIMULATED_OPT_IN, simulation_allowed


class EnclaveType(str, Enum):
    TPM_2_0 = "tpm_2_0"
    AMD_SEV_SNP = "amd_sev_snp"
    INTEL_TDX = "intel_tdx"
    AWS_NITRO = "aws_nitro"
    APPLE_SECURE_ENCLAVE = "apple_secure_enclave"
    SIMULATED = "simulated"


@dataclass(frozen=True)
class HardwareAttestationReport:
    enclave_type: EnclaveType
    measurement_digest: str
    is_valid: bool
    signer_id: str
    details: str
    status: str = NOT_EXECUTED


class HardwareAttestationVerifier:
    """Structural scaffold for hardware attestation envelopes (requires opt-in for simulation)."""

    @staticmethod
    def verify(
        attestation_dict: Dict[str, Any],
        allow_simulation: Optional[bool] = None,
    ) -> HardwareAttestationReport:
        if not attestation_dict:
            return HardwareAttestationReport(
                enclave_type=EnclaveType.SIMULATED,
                measurement_digest="",
                is_valid=False,
                signer_id="none",
                details="No hardware attestation provided",
                status=NOT_EXECUTED,
            )

        sim_ok = simulation_allowed(allow_simulation)
        if not sim_ok:
            return HardwareAttestationReport(
                enclave_type=EnclaveType.SIMULATED,
                measurement_digest="",
                is_valid=False,
                signer_id="unverified",
                details=(
                    "NOT_EXECUTED: No cryptographic AIK/VCEK/COSE signature verification is "
                    "implemented in this Python scaffold; length-only checks are refused by default."
                ),
                status=NOT_EXECUTED,
            )

        # Opt-in simulation mode only (structural length check, clearly labelled SIMULATED_OPT_IN):
        tpm_quote = attestation_dict.get("tpm_quote")
        if tpm_quote:
            digest = hashlib.sha256(str(tpm_quote).encode("utf-8")).hexdigest()
            return HardwareAttestationReport(
                enclave_type=EnclaveType.SIMULATED,
                measurement_digest=digest,
                is_valid=len(tpm_quote) >= 32,
                signer_id=attestation_dict.get("aik_id", "SIMULATED-AIK"),
                details="SIMULATED_OPT_IN: structural length check only (no TPM AIK signature verified)",
                status=SIMULATED_OPT_IN,
            )

        sev_snp = attestation_dict.get("sev_snp_measurement")
        if sev_snp:
            digest = hashlib.sha256(str(sev_snp).encode("utf-8")).hexdigest()
            return HardwareAttestationReport(
                enclave_type=EnclaveType.SIMULATED,
                measurement_digest=digest,
                is_valid=len(sev_snp) == 96 or len(sev_snp) >= 32,
                signer_id="SIMULATED-AMD-VCEK",
                details="SIMULATED_OPT_IN: structural length check only (no VCEK certificate chain verified)",
                status=SIMULATED_OPT_IN,
            )

        enclave_doc = attestation_dict.get("enclave_measurement")
        if enclave_doc:
            digest = hashlib.sha256(str(enclave_doc).encode("utf-8")).hexdigest()
            return HardwareAttestationReport(
                enclave_type=EnclaveType.SIMULATED,
                measurement_digest=digest,
                is_valid=len(enclave_doc) >= 32,
                signer_id="SIMULATED-NITRO",
                details="SIMULATED_OPT_IN: structural length check only (no COSE_Sign1 chain verified)",
                status=SIMULATED_OPT_IN,
            )

        return HardwareAttestationReport(
            enclave_type=EnclaveType.SIMULATED,
            measurement_digest="",
            is_valid=False,
            signer_id="unknown",
            details="Unrecognized enclave specification",
            status=NOT_EXECUTED,
        )
