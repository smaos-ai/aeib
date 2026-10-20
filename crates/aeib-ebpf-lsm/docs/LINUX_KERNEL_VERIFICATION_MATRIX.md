# Linux Kernel Version Matrix & eBPF LSM Verification Guide
## Technical Requirements, Verifier Constraints & Deployment Compatibility for AEIB eBPF LSM

> **Classification:** Pre-Production Kernel Substrate Specification (`crates/aeib-ebpf-lsm`)  
> **Epistemic Notice:** All capabilities described herein describe specifications and prototype interfaces evaluated under the stated model. In non-Linux or unprivileged test environments, a clean-room in-memory simulation controller evaluates identical state machine invariants.

---

### 1. Linux LTS Kernel Compatibility Matrix

To attach and enforce Ring 0 LSM hooks, the host Linux kernel must be compiled with `CONFIG_BPF_LSM=y` and expose BPF Type Format (BTF) debugging information (`CONFIG_DEBUG_INFO_BTF=y`).

| Kernel Version | Distribution Exemplars | LSM Availability | BTF / CO-RE | Sleepable LSM | Status / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Linux 6.1 LTS** | Debian 12 (Bookworm), RHEL 9.2+, Amazon Linux 2023 | Requires `lsm=...,bpf` in kernel boot parameters | Supported (`/sys/kernel/btf/vmlinux`) | Limited | **Supported Base Target**: All 4 core hooks (`bprm_check_security`, `file_mprotect`, `mmap_file`, `socket_connect`) functional. |
| **Linux 6.6 LTS** | Ubuntu 24.04 LTS, Debian 13 (Trixie testing) | Enabled by default in generic kernels | Native CO-RE support | Supported (`BPF_F_SLEEPABLE`) | **Recommended Production Target**: Optimal ring buffer performance and stable verifier bounds. |
| **Linux 6.12 LTS** | 2025/2026 Mainline Enterprise kernels | Enabled by default | Advanced BTF type tags | Full support | **Modern Target**: BPF Token support allows delegation of capability management to isolated namespaces. |

---

### 2. Kernel Configuration & Boot Parameter Requirements

#### 2.1 Mandatory Kernel Config Flags (`/boot/config-$(uname -r)`)
```ini
CONFIG_BPF=y
CONFIG_BPF_SYSCALL=y
CONFIG_BPF_JIT=y
CONFIG_BPF_LSM=y
CONFIG_DEBUG_INFO_BTF=y
CONFIG_SECURITY=y
CONFIG_SECURITY_NETWORK=y
```

#### 2.2 Bootloader Parameters (`/etc/default/grub`)
On distributions where BPF is not included in the default LSM list, ensure `bpf` is appended to the active LSM list:
```bash
GRUB_CMDLINE_LINUX="lsm=lockdown,capability,landlock,yama,apparmor,bpf"
```
Verify active LSM order at runtime:
```bash
cat /sys/kernel/security/lsm
# Expected output contains: capability,landlock,apparmor,bpf
```

---

### 3. Subsystem Interactions & Security Constraints

#### 3.1 Kernel Lockdown Mode (`/sys/kernel/security/lockdown`)
* **Integrity Mode (`lockdown=integrity`):**  
  Permitted. The kernel verifier prevents unsigned kprobes and arbitrary memory writes, but allows signed/verified BPF LSM programs that attach to designated LSM hooks.
* **Confidentiality Mode (`lockdown=confidentiality`):**  
  Restricted. `bpf_probe_read_kernel` is disabled. AEIB LSM programs use strict CO-RE direct field access (`BPF_CORE_READ`) which remains compatible with verifier safety bounds.

#### 3.2 Coexistence with SELinux & AppArmor
* AEIB eBPF LSM programs execute in an additive, fail-closed manner alongside primary MAC systems (SELinux or AppArmor).
* Under the Linux LSM framework, an operation is allowed **only if all registered LSMs return `0`**. If SELinux approves an execution but AEIB eBPF returns `-EPERM`, the execution is denied. Conversely, if AppArmor denies an action, AEIB cannot override the denial.

#### 3.3 MicroVM & Container Execution Constraints
* Inside an unprivileged container, direct access to `bpf(2)` syscall is typically blocked by default seccomp profiles.
* **Target Topology:** The AEIB eBPF LSM controller runs exclusively in the **host root namespace** with `CAP_SYS_ADMIN` or `CAP_BPF` + `CAP_PERFMON` + `CAP_NET_ADMIN`. Guest microVMs (e.g. Firecracker) run without BPF capabilities; their execution and sockets are monitored from the host kernel.

---

### 4. Linux Lifecycle Verification Command Sequence

To build, verify, load, and test the eBPF LSM program on a physical or virtual Linux host:

```bash
# 1. Verify Kernel BTF & LSM Support
test -f /sys/kernel/btf/vmlinux && echo "[✓] BTF available" || exit 1
grep -q "bpf" /sys/kernel/security/lsm && echo "[✓] BPF LSM active" || exit 1

# 2. Mount BPF Virtual Filesystem
sudo mount -t bpf bpf /sys/fs/bpf 2>/dev/null || true
sudo mkdir -p /sys/fs/bpf/aeib

# 3. Load CO-RE Bytecode and Capture Verifier Log
sudo bpftool prog load \
    crates/aeib-ebpf-lsm/target/bpfel-unknown-none/release/lsm_program.bin \
    /sys/fs/bpf/aeib/bprm_guard \
    type lsm hook bprm_check_security \
    --debug > output/ebpf_verifier_log.txt 2>&1

# 4. Attach Program Link
sudo bpftool link create \
    pinned /sys/fs/bpf/aeib/bprm_guard \
    pinned /sys/fs/bpf/aeib/link_bprm

# 5. Populate Policy Map (Pin Allowed Binary Inode)
INODE=$(stat -c '%i' /usr/local/bin/python3)
sudo bpftool map update \
    pinned /sys/fs/bpf/aeib/ALLOWED_EXECUTABLES \
    key hex 00 00 00 00 00 00 00 00 \
    value hex ...

# 6. Negative Invariant Test (Attempt Unregistered Binary Execution)
/tmp/unauthorized_agent_tool.sh
# Expected: Permission denied (errno 1: EPERM)

# 7. Clean Detach & Unpin
sudo rm -f /sys/fs/bpf/aeib/link_bprm
sudo rm -f /sys/fs/bpf/aeib/bprm_guard
sudo rm -rf /sys/fs/bpf/aeib
```
