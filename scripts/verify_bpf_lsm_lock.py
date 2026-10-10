#!/usr/bin/env python3
"""
verify_bpf_lsm_lock.py — 4-Axis Linux BPF-LSM & Kernel Lock Diagnostic Probe

Evaluates whether a Linux host has active BPF-LSM kernel enforcement, pinned BPF
policy maps, negative bpf(BPF_PROG_LOAD) syscall rejection (-EPERM), and
hardware attestation devices (Intel TDX / AMD SEV-SNP / TPM PCR 11).

Epistemic Note (AGENTS.md Section 5):
Code in `ebpf/` and `src/hardware_attestation.rs` in this repository is
structural scaffolding unless loaded into a Linux kernel with an active BPF
subsystem and CVM hardware. This diagnostic probe reports observed host kernel
facts without simulating or claiming live kernel enforcement when absent.
"""

import argparse
import ctypes
import errno
import json
import os
import pathlib
import platform
import stat
import sys
from typing import Any, Callable, Dict, List, Optional

BPF_PROG_LOAD = 5

# Linux syscall numbers for bpf() by architecture
SYS_BPF_BY_ARCH: Dict[str, int] = {
    "x86_64": 321,
    "amd64": 321,
    "aarch64": 280,
    "arm64": 280,
}


def inspect_lsm_and_lockdown(sysfs_root: pathlib.Path) -> Dict[str, Any]:
    """
    Axis 1: Inspects /sys/kernel/security/lsm and /sys/kernel/security/lockdown.
    """
    lsm_path = sysfs_root / "sys" / "kernel" / "security" / "lsm"
    lockdown_path = sysfs_root / "sys" / "kernel" / "security" / "lockdown"

    lsm_modules: List[str] = []
    bpf_lsm_active = False
    if lsm_path.is_file():
        raw_lsm = lsm_path.read_text(encoding="utf-8", errors="ignore").strip()
        lsm_modules = [m.strip() for m in raw_lsm.split(",") if m.strip()]
        bpf_lsm_active = "bpf" in lsm_modules

    lockdown_mode = "unavailable"
    lockdown_enforced = False
    if lockdown_path.is_file():
        raw_lockdown = lockdown_path.read_text(encoding="utf-8", errors="ignore").strip()
        lockdown_mode = raw_lockdown
        if "[confidentiality]" in raw_lockdown or "[integrity]" in raw_lockdown:
            lockdown_enforced = True

    return {
        "lsm_path": str(lsm_path),
        "lsm_modules_observed": lsm_modules,
        "bpf_lsm_active": bpf_lsm_active,
        "lockdown_mode_observed": lockdown_mode,
        "lockdown_enforced": lockdown_enforced,
        "passed": bpf_lsm_active and lockdown_enforced,
    }


def probe_negative_bpf_syscall(
    syscall_invoker: Optional[Callable[[int, int, int, int], int]] = None,
) -> Dict[str, Any]:
    """
    Axis 2: Executes a negative bpf(BPF_PROG_LOAD, NULL, 0) syscall probe.
    On a locked kernel, BPF_PROG_LOAD returns -EPERM (errno 1) or -EACCES (errno 13).
    """
    arch = platform.machine().lower()
    sys_nr = SYS_BPF_BY_ARCH.get(arch)

    if syscall_invoker is not None:
        err = syscall_invoker(sys_nr or 321, BPF_PROG_LOAD, 0, 0)
        blocked = err in (errno.EPERM, errno.EACCES)
        return {
            "platform": sys.platform,
            "architecture": arch,
            "syscall_number": sys_nr or 321,
            "observed_errno": err,
            "observed_errno_name": errno.errorcode.get(err, "UNKNOWN"),
            "passed": blocked,
        }

    if sys.platform != "linux" or sys_nr is None:
        return {
            "platform": sys.platform,
            "architecture": arch,
            "syscall_number": sys_nr,
            "observed_errno": None,
            "observed_errno_name": "NON_LINUX_HOST",
            "passed": False,
        }

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        syscall_fn = libc.syscall
        syscall_fn.restype = ctypes.c_long
        res = syscall_fn(
            ctypes.c_long(sys_nr),
            ctypes.c_int(BPF_PROG_LOAD),
            ctypes.c_void_p(0),
            ctypes.c_uint(0),
        )
        observed_errno = ctypes.get_errno() if res == -1 else 0
    except Exception as exc:
        return {
            "platform": sys.platform,
            "architecture": arch,
            "syscall_number": sys_nr,
            "observed_errno": None,
            "observed_errno_name": f"PROBE_ERROR:{exc}",
            "passed": False,
        }

    blocked = res == -1 and observed_errno in (errno.EPERM, errno.EACCES)
    return {
        "platform": sys.platform,
        "architecture": arch,
        "syscall_number": sys_nr,
        "observed_errno": observed_errno,
        "observed_errno_name": errno.errorcode.get(observed_errno, "OK"),
        "passed": blocked,
    }


def inspect_pinned_bpf_maps(
    sysfs_root: pathlib.Path,
    expected_maps: Optional[List[str]] = None,
    require_root_uid: bool = True,
) -> Dict[str, Any]:
    """
    Axis 3: Inspects /sys/fs/bpf for pinned policy maps and verifies restricted permissions (0600).
    """
    bpf_fs = sysfs_root / "sys" / "fs" / "bpf"
    targets = expected_maps if expected_maps is not None else [
        "model_weights_map",
        "allowed_binaries_map",
        "guard_events",
    ]

    if not bpf_fs.is_dir():
        return {
            "bpf_fs_path": str(bpf_fs),
            "bpf_fs_present": False,
            "maps": {},
            "passed": False,
        }

    maps_report: Dict[str, Any] = {}
    all_valid = True
    for name in targets:
        map_path = bpf_fs / name
        if not map_path.exists():
            maps_report[name] = {"exists": False, "passed": False}
            all_valid = False
            continue

        st = os.stat(map_path)
        mode_octal = stat.S_IMODE(st.st_mode)
        uid_ok = (st.st_uid == 0) if require_root_uid else True
        # Restricted permissions: no group/other access (e.g., 0600 or 0400)
        perm_ok = (mode_octal & 0o077) == 0 and (mode_octal in (0o600, 0o400))
        passed = uid_ok and perm_ok
        if not passed:
            all_valid = False
        maps_report[name] = {
            "exists": True,
            "uid": st.st_uid,
            "mode_octal": f"0{mode_octal:03o}",
            "passed": passed,
        }

    return {
        "bpf_fs_path": str(bpf_fs),
        "bpf_fs_present": True,
        "maps": maps_report,
        "passed": all_valid and bool(targets),
    }


def inspect_hardware_attestation(sysfs_root: pathlib.Path) -> Dict[str, Any]:
    """
    Axis 4: Checks CVM character devices (/dev/tdx_guest, /dev/sev-guest) and TPM PCR 11.
    """
    tdx_dev = sysfs_root / "dev" / "tdx_guest"
    tdx_alt = sysfs_root / "dev" / "tdx-guest"
    sev_dev = sysfs_root / "dev" / "sev-guest"
    tpm_pcr11 = sysfs_root / "sys" / "class" / "tpm" / "tpm0" / "pcr-sha256" / "11"
    ccel_acpi = sysfs_root / "sys" / "firmware" / "acpi" / "tables" / "CCEL"

    tdx_present = tdx_dev.exists() or tdx_alt.exists()
    sev_present = sev_dev.exists()
    pcr11_value: Optional[str] = None
    if tpm_pcr11.is_file():
        pcr11_value = tpm_pcr11.read_text(encoding="utf-8", errors="ignore").strip()

    pcr11_populated = bool(
        pcr11_value
        and len(pcr11_value) == 64
        and pcr11_value.strip("0") != ""
    )

    return {
        "tdx_device_present": tdx_present,
        "sev_snp_device_present": sev_present,
        "ccel_table_present": ccel_acpi.exists(),
        "tpm_pcr11_sha256": pcr11_value,
        "tpm_pcr11_populated": pcr11_populated,
        "passed": (tdx_present or sev_present) and (pcr11_populated or ccel_acpi.exists()),
    }


def evaluate_kernel_lock_posture(
    sysfs_root: pathlib.Path = pathlib.Path("/"),
    syscall_invoker: Optional[Callable[[int, int, int, int], int]] = None,
    require_root_uid: bool = True,
) -> Dict[str, Any]:
    """Runs all 4 diagnostic axes and returns a structured evaluation report."""
    axis1 = inspect_lsm_and_lockdown(sysfs_root)
    axis2 = probe_negative_bpf_syscall(syscall_invoker=syscall_invoker)
    axis3 = inspect_pinned_bpf_maps(sysfs_root, require_root_uid=require_root_uid)
    axis4 = inspect_hardware_attestation(sysfs_root)

    all_passed = axis1["passed"] and axis2["passed"] and axis3["passed"] and axis4["passed"]
    verdict = (
        "KERNEL_BPF_LSM_LOCK_OBSERVED"
        if all_passed
        else "ARCHITECTURAL_SCAFFOLD_OR_UNLOCKED_HOST"
    )

    return {
        "verdict": verdict,
        "all_axes_passed": all_passed,
        "epistemic_note": (
            "Per AGENTS.md Section 5, ebpf/ and hardware_attestation/ in the repository "
            "are structural scaffolding unless loaded on a Linux CVM kernel where all 4 axes pass."
        ),
        "axes": {
            "axis1_lsm_and_lockdown": axis1,
            "axis2_negative_bpf_syscall": axis2,
            "axis3_pinned_bpf_maps": axis3,
            "axis4_hardware_attestation": axis4,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="4-Axis Linux BPF-LSM & Kernel Lock Diagnostic Probe"
    )
    parser.add_argument(
        "--sysfs-root",
        type=pathlib.Path,
        default=pathlib.Path("/"),
        help="Root path for /sys and /dev inspection (default: /)",
    )
    parser.add_argument(
        "--require-enforced",
        action="store_true",
        help="Exit with code 1 if any of the 4 kernel enforcement axes is not active",
    )
    args = parser.parse_args()

    report = evaluate_kernel_lock_posture(sysfs_root=args.sysfs_root)
    print(json.dumps(report, indent=2))
    if args.require_enforced and not report["all_axes_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
