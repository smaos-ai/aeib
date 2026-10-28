"""Hardware CVM Attestation Probe (Intel TDX / AMD SEV-SNP) — Structural Scaffold.

Note: Opening `/dev/tdx_guest` or `/dev/sev-guest` without issuing the kernel
`TDX_CMD_GET_QUOTE` / `SNP_GET_REPORT` ioctl and verifying the platform quote
does NOT constitute hardware attestation. Until ioctl quote generation and PCK/VCEK
verification are wired, this scaffold never claims `hardware_attested`.
"""

from pathlib import Path


class HardwareAttestationUnavailable(RuntimeError):
    """Raised when hardware TEE character devices or ioctl bindings are unavailable."""


def get_hardware_quote(report_data: bytes) -> dict:
    _ = report_data
    tdx_dev = Path("/dev/tdx_guest")
    sev_dev = Path("/dev/sev-guest")

    if not tdx_dev.exists() and not sev_dev.exists():
        raise HardwareAttestationUnavailable(
            "Missing /dev/tdx_guest and /dev/sev-guest. "
            "AEIB refuses software-emulated attestation in strict mode."
        )

    raise HardwareAttestationUnavailable(
        "Character device present, but TDX_CMD_GET_QUOTE / SNP_GET_REPORT ioctl "
        "quote binding is not implemented in this Python module (status=NOT_EXECUTED)."
    )
