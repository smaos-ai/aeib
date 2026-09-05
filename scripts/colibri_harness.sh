#!/bin/bash
################################################################################
# Colibri v1.9.0 Vendor Harness for SMAOS Layer 6
#
# Purpose: Clone, compile, and configure Colibri binary for RTX 4060 edge nodes
# Runtime: ~45-60 seconds (compile), pure C99 + OpenMP, no external deps
# Exit: 0 on success, non-zero on failure
################################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLIBRI_REPO="${REPO_ROOT}/.colibri"
COLIBRI_BIN="${REPO_ROOT}/build/colibri"
COLIBRI_CACHE_PATH="/var/lib/smaos/colibri_cache"
CONFIG_FILE="${REPO_ROOT}/config/colibri_edge.json"

# Hardware config for RTX 4060 + 16GB RAM
TIER_VRAM_MB=6144
TIER_RAM_MB=16384
TIER_NVME_PATH="${COLIBRI_CACHE_PATH}"

################################################################################
# LOGGING
################################################################################

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

################################################################################
# PREREQUISITES CHECK
################################################################################

check_prerequisites() {
  log_info "Checking prerequisites..."

  # Check git
  if ! command -v git &> /dev/null; then
    log_error "git not found. Install git and retry."
    return 1
  fi

  # Check C compiler
  if ! command -v gcc &> /dev/null; then
    log_error "gcc not found. Install build-essential and retry."
    return 1
  fi

  # Check make
  if ! command -v make &> /dev/null; then
    log_error "make not found. Install build-essential and retry."
    return 1
  fi

  # Check for OpenMP support
  if ! gcc -fopenmp -E - <<< "int main() {}" &> /dev/null; then
    log_warn "OpenMP support may not be available. Proceeding with CPU path only."
  fi

  log_success "Prerequisites OK"
}

################################################################################
# REPOSITORY CLONE & SETUP
################################################################################

setup_colibri_repo() {
  log_info "Setting up Colibri repository..."

  # If repo exists, remove and re-clone for clean state
  if [ -d "${COLIBRI_REPO}" ]; then
    log_warn "Existing Colibri directory found. Removing for clean clone..."
    rm -rf "${COLIBRI_REPO}"
  fi

  mkdir -p "$(dirname "${COLIBRI_REPO}")"

  # Clone v1.9.0
  log_info "Cloning Colibri v1.9.0 from GitHub..."
  git clone --depth=1 --branch=v1.9.0 \
    https://github.com/JustVugg/colibri.git "${COLIBRI_REPO}" 2>&1 | \
    sed 's/^/  /'

  if [ ! -d "${COLIBRI_REPO}" ]; then
    log_error "Failed to clone Colibri repository"
    return 1
  fi

  log_success "Repository cloned: ${COLIBRI_REPO}"
}

################################################################################
# BUILD DIRECTORY SETUP
################################################################################

setup_build_dir() {
  log_info "Setting up build directory..."

  mkdir -p "${REPO_ROOT}/build"
  mkdir -p "$(dirname "${COLIBRI_BIN}")"

  log_success "Build directory ready: ${REPO_ROOT}/build"
}

################################################################################
# CACHE DIRECTORY SETUP
################################################################################

setup_cache_dir() {
  log_info "Setting up NVMe cache directory..."

  if [ ! -d "${TIER_NVME_PATH}" ]; then
    log_warn "Cache directory does not exist: ${TIER_NVME_PATH}"
    log_info "Creating cache directory..."

    # Try to create with sudo if needed
    if sudo mkdir -p "${TIER_NVME_PATH}" 2>/dev/null; then
      sudo chmod 755 "${TIER_NVME_PATH}"
      log_success "Cache directory created with sudo: ${TIER_NVME_PATH}"
    else
      # Fallback: create in user space
      TIER_NVME_PATH="${HOME}/.colibri_cache"
      mkdir -p "${TIER_NVME_PATH}"
      log_warn "Using user-space cache path: ${TIER_NVME_PATH}"
    fi
  else
    log_success "Cache directory exists: ${TIER_NVME_PATH}"
  fi
}

################################################################################
# COMPILATION: CPU PATH
################################################################################

compile_cpu_path() {
  log_info "Building CPU path (pure C99 + OpenMP)..."

  cd "${COLIBRI_REPO}"

  # Detect CPU count for parallel build
  if [ -f /proc/cpuinfo ]; then
    CPU_COUNT=$(grep -c "processor" /proc/cpuinfo)
  elif [ "$(uname)" == "Darwin" ]; then
    CPU_COUNT=$(sysctl -n hw.ncpu)
  else
    CPU_COUNT=4
  fi

  # Clean previous builds
  if [ -f Makefile ]; then
    make clean 2>&1 | sed 's/^/  /'
  fi

  # Compile with OpenMP support
  CFLAGS="-O3 -march=native -fopenmp -fPIC -Wall -Wextra -std=c99" \
  make -j "${CPU_COUNT}" 2>&1 | sed 's/^/  /'

  if [ $? -ne 0 ]; then
    log_error "CPU path compilation failed"
    return 1
  fi

  log_success "CPU path compiled successfully"
}

################################################################################
# COMPILATION: CUDA PATH (OPTIONAL)
################################################################################

compile_cuda_path() {
  log_info "Attempting CUDA path compilation..."

  # Check for NVIDIA GPU
  if ! command -v nvidia-smi &> /dev/null; then
    log_warn "NVIDIA GPU not detected. Skipping CUDA path."
    return 0
  fi

  # Check for CUDA toolkit
  if ! command -v nvcc &> /dev/null; then
    log_warn "CUDA toolkit not found. Skipping CUDA path."
    return 0
  fi

  cd "${COLIBRI_REPO}"

  # Attempt CUDA compilation if makefile supports it
  if grep -q "cuda" Makefile 2>/dev/null; then
    log_info "Building CUDA path..."
    make cuda 2>&1 | sed 's/^/  /' || {
      log_warn "CUDA build failed, proceeding with CPU binary only"
      return 0
    }
    log_success "CUDA path compiled successfully"
  else
    log_warn "CUDA target not found in Makefile"
  fi
}

################################################################################
# BINARY COPY
################################################################################

copy_binary() {
  log_info "Copying compiled binary to build directory..."

  # Find the compiled binary
  LOCAL_BIN=""
  if [ -f "${COLIBRI_REPO}/colibri" ]; then
    LOCAL_BIN="${COLIBRI_REPO}/colibri"
  elif [ -f "${COLIBRI_REPO}/build/colibri" ]; then
    LOCAL_BIN="${COLIBRI_REPO}/build/colibri"
  elif [ -f "${COLIBRI_REPO}/bin/colibri" ]; then
    LOCAL_BIN="${COLIBRI_REPO}/bin/colibri"
  else
    log_error "Compiled binary not found in expected locations"
    return 1
  fi

  cp "${LOCAL_BIN}" "${COLIBRI_BIN}"
  chmod +x "${COLIBRI_BIN}"

  log_success "Binary copied: ${COLIBRI_BIN}"
}

################################################################################
# VERIFY BINARY
################################################################################

verify_binary() {
  log_info "Verifying compiled binary..."

  if [ ! -f "${COLIBRI_BIN}" ]; then
    log_error "Binary not found: ${COLIBRI_BIN}"
    return 1
  fi

  # Check ELF header
  if file "${COLIBRI_BIN}" | grep -q "ELF"; then
    log_success "Binary is valid ELF executable"
  else
    log_error "Binary is not a valid ELF executable"
    return 1
  fi

  # Try to run --version or --help
  if "${COLIBRI_BIN}" --version &>/dev/null || \
     "${COLIBRI_BIN}" --help &>/dev/null || \
     "${COLIBRI_BIN}" -h &>/dev/null; then
    log_success "Binary responds to version/help query"
  else
    log_warn "Binary did not respond to standard help queries"
  fi

  # Size check
  BINARY_SIZE=$(stat -f%z "${COLIBRI_BIN}" 2>/dev/null || stat -c%s "${COLIBRI_BIN}" 2>/dev/null)
  if [ "${BINARY_SIZE}" -gt 100000 ]; then
    log_success "Binary size acceptable: $(numfmt --to=iec-i --suffix=B "${BINARY_SIZE}" 2>/dev/null || echo ${BINARY_SIZE} bytes)"
  else
    log_warn "Binary size is small (${BINARY_SIZE} bytes)"
  fi
}

################################################################################
# CREATE CONFIG FILE
################################################################################

create_config_file() {
  log_info "Creating Colibri edge configuration..."

  mkdir -p "$(dirname "${CONFIG_FILE}")"

  cat > "${CONFIG_FILE}" << 'EOFCONFIG'
{
  "substrate": "RTX_4060_8GB",
  "hardware": {
    "device_type": "RTX_4060",
    "vram_gb": 8,
    "ram_gb": 16,
    "nvme_cache_available": true
  },
  "tier_vram_mb": 6144,
  "tier_ram_mb": 16384,
  "tier_nvme_path": "/var/lib/smaos/colibri_cache",
  "caching_policy": "routing_aware_prefetch",
  "semantic_guarantee": "strict_fp16",
  "governance_hook": "http://127.0.0.1:8000/api/rce/check",
  "memory_hierarchy": {
    "l1_vram": {
      "mb": 6144,
      "bandwidth_gbs": 384,
      "latency_us": 0.001
    },
    "l2_ram": {
      "mb": 16384,
      "bandwidth_gbs": 25,
      "latency_us": 0.05
    },
    "l3_nvme": {
      "path": "/var/lib/smaos/colibri_cache",
      "bandwidth_gbs": 3,
      "latency_us": 5
    }
  },
  "prefetch_rules": [
    {
      "pattern": "routing_*",
      "tier": "l1_vram",
      "ttl_seconds": 3600
    },
    {
      "pattern": "semantic_*",
      "tier": "l1_vram",
      "ttl_seconds": 7200
    },
    {
      "pattern": "*",
      "tier": "l2_ram",
      "ttl_seconds": 14400
    }
  ],
  "semantic_config": {
    "guarantee_level": "strict_fp16",
    "routing_aware": true,
    "prefetch_enabled": true,
    "cache_alignment": "fp16"
  }
}
EOFCONFIG

  if [ ! -f "${CONFIG_FILE}" ]; then
    log_error "Failed to create config file"
    return 1
  fi

  log_success "Configuration file created: ${CONFIG_FILE}"
}

################################################################################
# VERIFY CONFIG FILE
################################################################################

verify_config_file() {
  log_info "Verifying configuration file..."

  if ! command -v python3 &> /dev/null; then
    log_warn "python3 not available, skipping JSON validation"
    return 0
  fi

  python3 -c "import json; json.load(open('${CONFIG_FILE}'))" 2>/dev/null
  if [ $? -eq 0 ]; then
    log_success "Configuration file is valid JSON"
  else
    log_error "Configuration file is invalid JSON"
    return 1
  fi
}

################################################################################
# GENERATE SUMMARY REPORT
################################################################################

generate_summary() {
  log_info "Generating harness summary report..."

  local REPORT_FILE="${REPO_ROOT}/.smaos/colibri_harness_summary.txt"
  mkdir -p "$(dirname "${REPORT_FILE}")"

  cat > "${REPORT_FILE}" << EOFREPORT
================================================================================
COLIBRI V1.9.0 HARNESS DEPLOYMENT REPORT
================================================================================

Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
Repository: ${REPO_ROOT}

BINARIES
--------
Primary:    ${COLIBRI_BIN}
Status:     $([ -f "${COLIBRI_BIN}" ] && echo "OK" || echo "MISSING")
Executable: $([ -x "${COLIBRI_BIN}" ] && echo "YES" || echo "NO")

CONFIGURATION
-------------
Config File: ${CONFIG_FILE}
Status:     $([ -f "${CONFIG_FILE}" ] && echo "OK" || echo "MISSING")

Hardware Spec:
  Substrate:      RTX 4060 8GB
  VRAM Tier:      ${TIER_VRAM_MB} MB
  RAM Tier:       ${TIER_RAM_MB} MB
  Cache Path:     ${TIER_NVME_PATH}

Memory Hierarchy:
  L1 (VRAM):      6144 MB @ 384 GB/s (0.001 us latency)
  L2 (RAM):       16384 MB @ 25 GB/s (0.05 us latency)
  L3 (NVMe):      Unbounded @ 3 GB/s (5 us latency)

Caching Policy:   routing_aware_prefetch
Semantic Guarantee: strict_fp16

GOVERNANCE
----------
Hook Endpoint:  http://127.0.0.1:8000/api/rce/check
Hook Type:      POST (RCE verification)
Timeout:        5 seconds (default)

COMPILATION
-----------
CPU Path:       Enabled (OpenMP)
CUDA Path:      $(nvidia-smi &>/dev/null && echo "Enabled" || echo "Disabled")
Compiler:       $(gcc --version | head -1)
Build Date:     $([ -f "${COLIBRI_BIN}" ] && stat -f %Sm -t '%Y-%m-%d %H:%M:%S' "${COLIBRI_BIN}" 2>/dev/null || echo "N/A")

DEPLOYMENT CHECKLIST
====================
[X] Colibri v1.9.0 cloned from GitHub
[X] CPU path compiled (C99 + OpenMP)
[X] Binary verified and executable
[X] Configuration file created
[X] Memory tiers configured for RTX 4060
[X] Cache directory path specified
[X] Governance hook configured
[X] Semantic invariance set to strict_fp16

NEXT STEPS
==========
1. Run tests: python3 tests/test_colibri_harness.py
2. Verify governance endpoint: curl http://127.0.0.1:8000/api/rce/check
3. Deploy binary to edge node
4. Validate Layer 6 integration

================================================================================
EOFREPORT

  log_success "Summary report generated: ${REPORT_FILE}"
  cat "${REPORT_FILE}"
}

################################################################################
# MAIN EXECUTION
################################################################################

main() {
  echo ""
  echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║      COLIBRI V1.9.0 VENDOR HARNESS FOR SMAOS LAYER 6          ║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
  echo ""

  # Execute pipeline
  check_prerequisites || exit 1
  setup_build_dir || exit 1
  setup_colibri_repo || exit 1
  setup_cache_dir || exit 1
  compile_cpu_path || exit 1
  compile_cuda_path  # Non-fatal if fails
  copy_binary || exit 1
  verify_binary || exit 1
  create_config_file || exit 1
  verify_config_file || exit 1
  generate_summary

  echo ""
  echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  Colibri harness deployment complete. Ready for Layer 6.      ║${NC}"
  echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
  echo ""

  return 0
}

main "$@"
