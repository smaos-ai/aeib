#!/usr/bin/env python3
"""
test_bpf_lsm_lock_probe.py — Unit & Falsifiability Tests for 4-Axis BPF-LSM Kernel Probe
"""

import errno
import os
import pathlib
from scripts.verify_bpf_lsm_lock import evaluate_kernel_lock_posture


def _populate_sysfs_tree(
    root: pathlib.Path,
    lsm_content: str = "lockdown,capability,yama,apparmor,bpf\n",
    lockdown_content: str = "none integrity [confidentiality]\n",
    map_mode: int = 0o600,
    include_tdx: bool = True,
    pcr11_hex: str = "a3f5c8e91204b7d681239405a3f5c8e91204b7d681239405a3f5c8e91204b7d6",
) -> None:
    sec_dir = root / "sys" / "kernel" / "security"
    sec_dir.mkdir(parents=True, exist_ok=True)
    (sec_dir / "lsm").write_text(lsm_content, encoding="utf-8")
    (sec_dir / "lockdown").write_text(lockdown_content, encoding="utf-8")

    bpf_dir = root / "sys" / "fs" / "bpf"
    bpf_dir.mkdir(parents=True, exist_ok=True)
    for map_name in ("model_weights_map", "allowed_binaries_map", "guard_events"):
        mpath = bpf_dir / map_name
        mpath.write_bytes(b"\x00" * 16)
        os.chmod(mpath, map_mode)

    if include_tdx:
        dev_dir = root / "dev"
        dev_dir.mkdir(parents=True, exist_ok=True)
        (dev_dir / "tdx_guest").write_bytes(b"\x01" * 64)

    pcr_dir = root / "sys" / "class" / "tpm" / "tpm0" / "pcr-sha256"
    pcr_dir.mkdir(parents=True, exist_ok=True)
    (pcr_dir / "11").write_text(pcr11_hex + "\n", encoding="utf-8")


def test_all_four_axes_pass_when_locked(tmp_path: pathlib.Path) -> None:
    _populate_sysfs_tree(tmp_path)
    report = evaluate_kernel_lock_posture(
        sysfs_root=tmp_path,
        syscall_invoker=lambda _nr, _cmd, _attr, _sz: errno.EPERM,
        require_root_uid=False,
    )
    assert report["all_axes_passed"] is True
    assert report["verdict"] == "KERNEL_BPF_LSM_LOCK_OBSERVED"
    assert report["axes"]["axis1_lsm_and_lockdown"]["bpf_lsm_active"] is True
    assert report["axes"]["axis2_negative_bpf_syscall"]["observed_errno"] == errno.EPERM
    assert report["axes"]["axis3_pinned_bpf_maps"]["passed"] is True
    assert report["axes"]["axis4_hardware_attestation"]["passed"] is True


def test_fails_closed_when_bpf_missing_from_lsm_stack(tmp_path: pathlib.Path) -> None:
    _populate_sysfs_tree(tmp_path, lsm_content="lockdown,capability,yama,apparmor\n")
    report = evaluate_kernel_lock_posture(
        sysfs_root=tmp_path,
        syscall_invoker=lambda _nr, _cmd, _attr, _sz: errno.EPERM,
        require_root_uid=False,
    )
    assert report["axes"]["axis1_lsm_and_lockdown"]["bpf_lsm_active"] is False
    assert report["all_axes_passed"] is False
    assert report["verdict"] == "ARCHITECTURAL_SCAFFOLD_OR_UNLOCKED_HOST"


def test_fails_closed_when_bpf_syscall_not_blocked(tmp_path: pathlib.Path) -> None:
    _populate_sysfs_tree(tmp_path)
    report = evaluate_kernel_lock_posture(
        sysfs_root=tmp_path,
        syscall_invoker=lambda _nr, _cmd, _attr, _sz: 0,
        require_root_uid=False,
    )
    assert report["axes"]["axis2_negative_bpf_syscall"]["passed"] is False
    assert report["all_axes_passed"] is False


def test_fails_closed_when_pinned_map_world_writable(tmp_path: pathlib.Path) -> None:
    _populate_sysfs_tree(tmp_path, map_mode=0o666)
    report = evaluate_kernel_lock_posture(
        sysfs_root=tmp_path,
        syscall_invoker=lambda _nr, _cmd, _attr, _sz: errno.EPERM,
        require_root_uid=False,
    )
    assert report["axes"]["axis3_pinned_bpf_maps"]["passed"] is False
    assert report["all_axes_passed"] is False


def test_fails_closed_when_cvm_device_absent(tmp_path: pathlib.Path) -> None:
    _populate_sysfs_tree(tmp_path, include_tdx=False)
    report = evaluate_kernel_lock_posture(
        sysfs_root=tmp_path,
        syscall_invoker=lambda _nr, _cmd, _attr, _sz: errno.EPERM,
        require_root_uid=False,
    )
    assert report["axes"]["axis4_hardware_attestation"]["passed"] is False
    assert report["all_axes_passed"] is False
