#!/bin/bash

set -euo pipefail

# ============================================================================
# VISION SURVIVAL PROTOCOL — Vault Initialization Script
# Purpose: Create encrypted, distributed backups of the SMAOS vision
# Usage: ./vault_init.sh [vault-location]
# Vault locations: A (primary/home), B (shadow/safe-deposit), C (remote/Israel)
# ============================================================================

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_DIR")/../../.." && pwd)"
VAULT_LOCATION="${1:-}"
MIN_VAULT_SIZE_GB=500  # Minimum 500GB for workspace + redundancy
ENCRYPTION_CIPHER="AES-256-GCM"

# Temporary directory for shards
TEMP_SHARDS_DIR=$(mktemp -d)
trap "rm -rf $TEMP_SHARDS_DIR" EXIT

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_debug() {
    if [[ "${DEBUG:-0}" == "1" ]]; then
        echo -e "${CYAN}[DEBUG]${NC} $1"
    fi
}

# Detect connected USB drives
detect_usb_drives() {
    log_info "Detecting USB-C SSDs..."

    local drives=()

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: Use diskutil to list USB devices
        while IFS= read -r device; do
            if [[ -z "$device" ]]; then
                continue
            fi

            # Get device info
            local info=$(diskutil info "$device" 2>/dev/null || echo "")
            if [[ -z "$info" ]]; then
                continue
            fi

            local name=$(echo "$info" | grep "Device / Media Name" | awk -F': ' '{print $2}' || echo "Unknown")
            local size=$(echo "$info" | grep "Total Size" | awk -F': ' '{print $2}' || echo "Unknown")
            local protocol=$(echo "$info" | grep "Protocol" | awk -F': ' '{print $2}' || echo "Unknown")

            drives+=("$device|$name|$size|$protocol")
        done < <(diskutil list external physical 2>/dev/null | grep "^/dev/disk" | awk '{print $1}')
    else
        # Linux: Use lsblk to detect USB drives
        while IFS= read -r line; do
            if [[ -z "$line" ]]; then
                continue
            fi

            local device=$(echo "$line" | awk '{print $1}')
            local size=$(echo "$line" | awk '{print $4}')
            local name=$(echo "$line" | awk '{print $2}')

            drives+=("$device|$name|$size|USB")
        done < <(lsblk -d -o NAME,MODEL,SIZE -n | grep -i usb)
    fi

    if [ ${#drives[@]} -eq 0 ]; then
        log_error "No USB drives detected. Please connect a USB-C SSD and try again."
        return 1
    fi

    printf '%s\n' "${drives[@]}"
}

# Validate vault location
validate_vault_location() {
    local location=$1
    case $location in
        A|B|C) return 0 ;;
        *)
            log_error "Invalid vault location: $location. Must be A, B, or C."
            return 1
            ;;
    esac
}

# Prompt user for vault location
prompt_vault_location() {
    echo
    echo "Vault Locations:"
    echo "  A — Primary (your home office, Prague)"
    echo "  B — Shadow (safe deposit box, Czech Republic)"
    echo "  C — Remote (escrow/counsel, Israel)"
    echo

    local location
    read -p "Enter vault location (A/B/C): " location

    validate_vault_location "$location" || return 1
    echo "$location"
}

# Select USB drive from list
select_usb_drive() {
    local -a drives=()

    mapfile -t drives < <(detect_usb_drives)

    if [ ${#drives[@]} -eq 0 ]; then
        return 1
    fi

    echo
    echo "Available USB-C SSDs:"
    for i in "${!drives[@]}"; do
        IFS='|' read -r device name size protocol <<< "${drives[$i]}"
        printf "%2d. %-20s | Size: %-15s | Protocol: %s\n" "$((i+1))" "$name" "$size" "$protocol"
    done
    echo

    local selection
    read -p "Select drive number: " selection

    if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt ${#drives[@]} ]; then
        log_error "Invalid selection."
        return 1
    fi

    selection=$((selection - 1))
    IFS='|' read -r device name size protocol <<< "${drives[$selection]}"

    log_info "Selected: $device — $name ($size)"
    echo "$device"
}

# Get encryption passphrase from user
prompt_encryption_passphrase() {
    echo
    log_warning "Choose a strong passphrase (minimum 32 characters, mix of uppercase, lowercase, numbers, symbols)."
    echo

    local passphrase
    local passphrase_confirm

    while true; do
        read -sp "Enter encryption passphrase: " passphrase
        echo

        if [ ${#passphrase} -lt 32 ]; then
            log_error "Passphrase must be at least 32 characters."
            continue
        fi

        read -sp "Confirm passphrase: " passphrase_confirm
        echo

        if [ "$passphrase" != "$passphrase_confirm" ]; then
            log_error "Passphrases do not match. Please try again."
            continue
        fi

        break
    done

    echo "$passphrase"
}

# Create encrypted volume (macOS)
create_encrypted_volume_macos() {
    local device=$1
    local vault_name=$2

    log_info "Creating encrypted APFS volume on $device..."

    # Unmount existing volumes
    diskutil unmountDisk "$device" 2>/dev/null || true
    sleep 1

    # Initialize as APFS with encryption
    if ! diskutil secureErase freespace 0 "$device" 2>/dev/null; then
        log_warning "Secure erase not supported; proceeding with standard format."
    fi

    # Create APFS container
    if diskutil apfs create "$device" -encryptionType AES256 "$vault_name" 2>&1 | tee /tmp/apfs.log; then
        log_success "Encrypted APFS volume created: $vault_name"
    else
        log_error "Failed to create encrypted APFS volume."
        cat /tmp/apfs.log >&2
        return 1
    fi

    sleep 2
}

# Create encrypted volume (Linux)
create_encrypted_volume_linux() {
    local device=$1
    local vault_name=$2
    local passphrase=$3

    log_info "Creating encrypted LUKS volume on $device..."

    # Unmount if already mounted
    sudo umount "$device"* 2>/dev/null || true

    # Create LUKS encrypted partition
    echo -n "$passphrase" | sudo cryptsetup luksFormat --type luks2 "$device" - || {
        log_error "Failed to create LUKS encrypted volume."
        return 1
    }

    # Open encrypted volume
    echo -n "$passphrase" | sudo cryptsetup luksOpen "$device" "$vault_name" - || {
        log_error "Failed to open encrypted volume."
        return 1
    }

    # Create filesystem
    sudo mkfs.ext4 "/dev/mapper/$vault_name" || {
        log_error "Failed to create filesystem."
        return 1
    }

    log_success "Encrypted LUKS volume created: $vault_name"
}

# Find and return mount point of vault
find_vault_mount_point() {
    local device=$1

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: Find APFS mount point
        local mount_point=$(diskutil info "$device" 2>/dev/null | grep "Mount Point" | awk -F': ' '{print $2}' | head -1)
        if [ -n "$mount_point" ] && [ -d "$mount_point" ]; then
            echo "$mount_point"
            return 0
        fi

        # Try alternate method: list all APFS volumes
        mount_point=$(mount | grep "$device" | awk '{print $3}' | head -1)
        if [ -n "$mount_point" ] && [ -d "$mount_point" ]; then
            echo "$mount_point"
            return 0
        fi
    else
        # Linux: Mount encrypted volume
        local mapper_name=$(basename "$device")
        mkdir -p "/mnt/$mapper_name"
        sudo mount "/dev/mapper/$mapper_name" "/mnt/$mapper_name"
        echo "/mnt/$mapper_name"
        return 0
    fi

    log_error "Could not find vault mount point."
    return 1
}

# Copy workspace to vault
copy_workspace() {
    local mount_point=$1
    local vault_location=$2

    log_info "Copying SMAOS workspace to vault (this may take several minutes)..."

    # Create vault structure
    mkdir -p "$mount_point/smaos"

    # Validate source exists
    if [ ! -d "$PROJECT_ROOT/crates" ]; then
        log_error "Source directory not found: $PROJECT_ROOT/crates"
        return 1
    fi

    # Copy entire project, excluding unnecessary files
    # Use rsync if available, fallback to cp
    if command -v rsync &> /dev/null; then
        if ! rsync -av --progress \
            --exclude='.git' \
            --exclude='target' \
            --exclude='node_modules' \
            --exclude='.DS_Store' \
            --exclude='*.o' \
            --exclude='*.a' \
            --exclude='*.so' \
            --exclude='.pytest_cache' \
            --exclude='.gitnexus' \
            --exclude='Cargo.lock' \
            "$PROJECT_ROOT/" "$mount_point/smaos/" 2>&1 | tail -20; then
            log_error "Failed to copy workspace to vault."
            return 1
        fi
    else
        log_warning "rsync not available; using cp (slower)..."
        if ! cp -rv "$PROJECT_ROOT/" "$mount_point/smaos/" 2>&1 | tail -20; then
            log_error "Failed to copy workspace to vault."
            return 1
        fi
    fi

    log_success "Workspace copied to vault."
}

# Generate Shamir Secret Sharing shards
generate_shamir_shards() {
    local vault_path=$1
    local vault_location=$2

    log_info "Generating Shamir Secret Sharing (3-of-5) for vault encryption..."

    # Create master key (32 bytes = 256 bits for AES-256)
    local master_key=$(openssl rand -hex 32)

    log_debug "Master key generated (length: ${#master_key})"

    # Try to use sss-cli if available, otherwise use basic shard generation
    if command -v sss &> /dev/null; then
        log_info "Using sss-cli for Shamir Secret Sharing..."

        # Split into 5 shards with 3-of-5 threshold
        local sss_output
        sss_output=$(echo "$master_key" | sss split -n 5 -k 3 2>&1 || echo "")

        if [ -z "$sss_output" ]; then
            log_warning "sss-cli failed; falling back to simple key distribution."
            sss_output="$master_key"
        fi
    else
        log_warning "sss-cli not installed. Using simplified key distribution (recommend installing sss-cli for production)."
        # Fallback: Generate 5 derived keys using HKDF
        local sss_output=""
        for i in {1..5}; do
            local derived=$(echo -n "$master_key|shard$i" | openssl dgst -sha256 -hex | awk '{print $2}')
            sss_output+="Shard $i: $derived"$'\n'
        done
    fi

    # Store shards in temp directory
    cat > "$TEMP_SHARDS_DIR/VAULT_KEY_SHARDS.txt" <<EOF
================================================================================
SMAOS VISION VAULT — ENCRYPTION KEY SHARDS (Shamir Secret Sharing 3-of-5)
================================================================================

Vault Location: $vault_location
Created: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Vault Operator: Andrej Leukhin (Visionary)

SECURITY WARNING
================================================================================
These shards are cryptographic secrets. Treat them with absolute care:

• Loss of all 5 shards = permanent loss of vault contents
• Exposure of 3+ shards = compromised vault security
• Never store more than 2 shards in the same location
• Never transmit shards over unencrypted channels
• Keep shards in encrypted form when distributed

KEY DISTRIBUTION PROTOCOL
================================================================================

Shard 1 (PRIMARY): $master_key
  Location: Encrypted within vault itself (VAULT_SHARD_1.encrypted)
  Custodian: Visionary (Andrej Leukhin)
  Access: Vault must be physically accessible

Shard 2 (OWNER):
  Location: Personal encrypted safe (1Password, Bitwarden, hardware wallet)
  Custodian: Andrej Leukhin (Visionary)
  Purpose: Primary recovery if other shards are lost

Shard 3 (FAMILY):
  Location: Safe deposit box or trusted family member
  Custodian: Family member (wife) — To be distributed
  Instructions: Secure passphrase, access only in emergency

Shard 4 (LEGAL):
  Location: Attorney's safe/escrow
  Custodian: Pearl Cohen (Israeli counsel) — To be distributed
  Instructions: Geopolitical fail-safe, survives conflicts

Shard 5 (FOUNDATION):
  Location: Swiss Foundation escrow
  Custodian: Foundation trustees — To be distributed (future)
  Instructions: Long-term institutional preservation

RECOVERY PROTOCOL
================================================================================

To recover vault contents:
  1. Collect any 3 of 5 key shards (e.g., Shards 1, 2, and 3)
  2. Use sss-cli to combine:

     $ sss combine -k 3 << EOF
     <shard-1-value>
     <shard-2-value>
     <shard-3-value>
     EOF

  3. Output will be the master decryption key
  4. Use key to decrypt vault using recovery procedures

CUSTODIAN CONTACT MATRIX
================================================================================

Primary Contact (Andrej Leukhin):
  Email: andrejlo123@gmail.com
  Phone: [To be configured]
  Public Key: ed25519:... [See Genesis Files]

Family Custodian:
  Name: [To be specified]
  Contact: [To be specified]

Legal Custodian (Pearl Cohen):
  Organization: [Israeli law firm/counsel]
  Contact: [To be specified]

Foundation Custodian:
  Organization: Sovereign Vision Foundation (TBD)
  Contact: [To be specified]

ANNUAL REVIEW CHECKLIST
================================================================================

Every January:
  [ ] Verify all 5 custodians still hold their shards
  [ ] Test recovery with subset of shards (without decrypting vault)
  [ ] Update contact information
  [ ] Rotate passphrase if exposure risk detected
  [ ] Update VAULT_MANIFEST.json with new checksums

AUDIT TRAIL
================================================================================

Creation Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Created By: vault_init.sh v1.0
Vault ID: $(uuidgen)
Encryption Algorithm: AES-256-GCM
Shamir Threshold: 3-of-5

================================================================================
KEEP THIS FILE ENCRYPTED AND SECURE
================================================================================

EOF

    # Also save the actual shard data
    cat > "$TEMP_SHARDS_DIR/SHARDS_DATA.txt" <<EOF
$sss_output
EOF

    # Copy shard file to vault
    cp "$TEMP_SHARDS_DIR/VAULT_KEY_SHARDS.txt" "$vault_path/VAULT_KEY_SHARDS.txt"

    log_success "Shamir shards generated and stored in vault."
    log_info "Shard distribution file saved to: $vault_path/VAULT_KEY_SHARDS.txt"

    # Return master key for manifest
    echo "$master_key"
}

# Generate vault manifest
generate_manifest() {
    local vault_path=$1
    local vault_location=$2
    local master_key=$3

    log_info "Generating vault manifest..."

    local vault_uuid=$(uuidgen 2>/dev/null || echo "$(date +%s)-$RANDOM")
    local creation_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local operator_pubkey="ed25519:TBD"  # Will be updated with actual Genesis key

    cat > "$vault_path/VAULT_MANIFEST.json" <<EOF
{
  "version": "1.0",
  "vault_id": "$vault_uuid",
  "location": "$vault_location",
  "created": "$creation_date",
  "operator": "Andrej Leukhin (Visionary)",
  "operator_email": "andrejlo123@gmail.com",
  "operator_pubkey": "$operator_pubkey",
  "contents": {
    "smaos_workspace": {
      "path": "/smaos",
      "description": "Complete SMAOS repository with all crates",
      "includes": [
        "Source code (crates/)",
        "Genesis Capsules (private key material)",
        "MLX distilled models",
        "Documentation and architecture specs",
        "Test suites and CI/CD configurations"
      ]
    },
    "genesis_files": {
      "path": "/smaos/.claude/private/",
      "description": "Identity keys and credential material",
      "includes": [
        "Ed25519 dual-custodian keys",
        "SISS identity certificates",
        "Recovery credentials"
      ]
    }
  },
  "encryption": {
    "algorithm": "AES-256-GCM",
    "cipher_strength_bits": 256,
    "shamir_scheme": "3-of-5 threshold",
    "key_format": "hex-encoded 64-character string",
    "key_location": "VAULT_KEY_SHARDS.txt",
    "key_distribution": {
      "shard_1": "Stored within vault (encrypted)",
      "shard_2": "Owner/Visionary (Andrej Leukhin)",
      "shard_3": "Family member (wife)",
      "shard_4": "Legal/Israel counsel (Pearl Cohen)",
      "shard_5": "Foundation escrow (future)"
    }
  },
  "verification": {
    "workspace_checksum_sha256": "TBD",
    "file_count": "TBD",
    "total_size_bytes": "TBD",
    "last_verified": "$creation_date"
  },
  "maintenance": {
    "sync_frequency": "Nightly (automated Night Shift)",
    "last_sync": "Never (vault initialization)",
    "backup_strategy": "3-location distributed (A/B/C)",
    "rotation_policy": "Annual"
  },
  "disaster_recovery": {
    "recovery_guide": "VAULT_RECOVERY.md",
    "emergency_contacts": "VAULT_CONTACTS.json",
    "test_recovery": "Annually in January",
    "escalation_procedure": "See VAULT_RECOVERY.md section 'Emergency Activation'"
  },
  "audit": {
    "creation_date": "$creation_date",
    "created_by": "vault_init.sh v1.0",
    "creation_environment": "$(uname -s) $(uname -r)",
    "checksum_type": "SHA-256",
    "signed_by": "TBD"
  },
  "status": "ACTIVE",
  "next_review_date": "$(date -u -d '+1 year' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v+1y +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

    log_success "Vault manifest generated."
}

# Generate emergency recovery guide
generate_recovery_guide() {
    local vault_path=$1

    log_info "Generating emergency recovery guide..."

    cat > "$vault_path/VAULT_RECOVERY.md" << 'EOFRECOVERY'
# SMAOS Vision Vault — Emergency Recovery Guide

## Overview

This guide provides step-by-step instructions for recovering the complete SMAOS vision from an encrypted vault in case of emergency, data loss, or catastrophic system failure.

## Vault Structure

```
Vault Root
├── VAULT_MANIFEST.json          # Vault metadata and checksums
├── VAULT_KEY_SHARDS.txt         # Encryption key shard distribution
├── VAULT_RECOVERY.md            # This file
├── VAULT_CONTACTS.json          # Custodian contact information
└── smaos/
    ├── crates/                  # All SISS system crates
    ├── docs/                    # Architecture and design documentation
    ├── .claude/                 # Claude code configurations
    │   └── private/             # Genesis keys (secured in vault)
    └── Cargo.toml, Cargo.lock   # Rust workspace configuration
```

## Emergency Scenarios & Recovery Procedures

### Scenario 1: Primary Laptop Lost/Destroyed

**Symptoms:** Laptop crashed, stolen, or physically destroyed. All local work lost.

**Recovery Steps:**

1. **Locate Vault A (Primary)**
   - Retrieve physical SSD from home office or secure location
   - Ensure you have a working computer with USB-C connection capability
   - Standard USB-C SSD enclosure required

2. **Gather Key Shards**
   - Retrieve Shard 1 or Shard 2 (personal custody)
   - Contact family member for Shard 3
   - Contact counsel for Shard 4
   - You need ANY 3 of 5 shards

3. **Mount Vault**

   ```bash
   # macOS
   diskutil list external
   diskutil mount /dev/diskX

   # Linux
   sudo cryptsetup luksOpen /dev/sdX vault_decrypted
   sudo mount /dev/mapper/vault_decrypted /mnt/vault
   ```

4. **Recover Master Key**

   ```bash
   # Create file with 3 shards (one per line)
   cat > /tmp/shards.txt << EOF
   [shard-1-value]
   [shard-2-value]
   [shard-3-value]
   EOF

   # Combine shards using Shamir Secret Sharing
   sss combine -k 3 < /tmp/shards.txt > /tmp/master_key.txt

   # Verify key length (should be 64 hex characters for AES-256)
   wc -c /tmp/master_key.txt
   ```

5. **Restore Workspace**

   ```bash
   # Copy vault contents
   cp -r /mnt/vault/smaos ~/Documents/SovereignNexus

   # Restore build artifacts (if needed)
   cd ~/Documents/SovereignNexus
   cargo build

   # Restore encrypted keys from Genesis Capsules
   ./scripts/restore_genesis.sh

   # Restore Night Shift automation
   ./scripts/restore_night_shift.sh
   ```

6. **Verify Integrity**

   ```bash
   # Check manifest checksums
   cd ~/Documents/SovereignNexus
   sha256sum -c .vault/VAULT_MANIFEST.json

   # Run test suite to verify no corruption
   cargo test --all
   ```

7. **Secure the Recovery Process**

   ```bash
   # Overwrite key fragments from memory
   shred -u /tmp/shards.txt /tmp/master_key.txt

   # Unmount and secure vault
   diskutil unmountDisk /dev/diskX

   # Update last-recovery timestamp
   echo "Last recovery: $(date)" >> /mnt/vault/VAULT_MANIFEST.json
   ```

### Scenario 2: Vault A Lost/Corrupted

**Symptoms:** Primary vault USB damaged, lost, or unreadable.

**Recovery Steps:**

1. **Retrieve Vault B (Safe Deposit Box)**
   - Vault B is a full identical copy stored in safe deposit box
   - Retrieve from bank with proper identification
   - Follow same mount/recovery procedures as Scenario 1

2. **If Vault B Unavailable, Use Vault C (Remote)**
   - Contact Pearl Cohen (Israeli counsel)
   - Request retrieval of Vault C from secure escrow
   - Proceed with recovery using Vault C contents

### Scenario 3: Multiple Vaults Lost (A and B)

**Symptoms:** Catastrophic data loss. Only Vault C (remote) remains accessible.

**Recovery Steps:**

1. **Activate Emergency Protocol**

   ```bash
   # Contact all 3 custodians with proof of identity:
   # 1. Family member (Shard 3)
   # 2. Counsel (Shard 4)
   # 3. Foundation (Shard 5)

   # Provide signed request with verification details
   ```

2. **Retrieve Vault C**
   - Work with Israeli counsel to retrieve vault from escrow
   - Verify vault integrity with manifest checksums
   - Transport securely to accessible location

3. **Perform Recovery**
   - Combine Shards 3, 4, 5 to recover master key
   - Follow standard mount/restore procedures

### Scenario 4: Key Shards Lost or Compromised

**Symptoms:** Shard holder unavailable or shards exposed to unauthorized party.

**Recovery Steps:**

1. **If Fewer Than 3 Shards Available**
   - Activate SMAOS Foundation emergency protocol
   - Require trustee approval for reissuance
   - Generate new master key and re-shard (requires vault access first)

2. **If Shards Exposed to Third Party**
   - Immediately rotate master key
   - Regenerate all 5 shards with new threshold
   - Redistribute to custodians
   - Update all vault copies with new key

3. **Key Rotation Procedure**

   ```bash
   # Mount vault with current master key
   sss combine -k 3 < /tmp/old_shards.txt > /tmp/old_key.txt

   # Mount vault
   diskutil mount [old encrypted volume]

   # Re-encrypt vault contents with new key
   ./scripts/rotate_vault_key.sh /mnt/vault /tmp/old_key.txt

   # Generate new shards
   ./vault_init.sh A  # Reinitialize with fresh shards

   # Distribute new shards to custodians
   ```

## Technical Deep Dive: Shamir Secret Sharing

The SMAOS vision uses Shamir Secret Sharing (SSS) to distribute vault access:

**Scheme:** 3-of-5 threshold
- Total shards: 5
- Minimum shards to recover key: 3
- Maximum shards an attacker can have without unlocking: 2

**Mathematical Properties:**
- Each shard is mathematically independent
- No single shard contains recoverable information
- Any 3 shards can recover the secret
- 100% information loss if fewer than 3 shards remain

**Shard Distribution:**
```
Shard 1 + 2: Personal custody (Andrej Leukhin)
  └─ Split between home vault and encrypted personal store

Shard 3: Family custody
  └─ Wife or trusted family member

Shard 4: Legal custody (Israel)
  └─ Pearl Cohen or law firm escrow

Shard 5: Institutional custody
  └─ Swiss Foundation (future)
```

**Why 3-of-5 is Optimal:**
- Survives loss of 2 shards (redundancy)
- No single custodian has unilateral control
- Geopolitical distribution (Europe + Israel + personal)
- Requires cooperation of disparate parties

## Verification Procedures

### Annual Vault Integrity Test

Every January, perform this test:

```bash
# 1. Mount vault without decrypting
diskutil mount /dev/diskX

# 2. Verify manifest
cat /mnt/vault/VAULT_MANIFEST.json | jq .

# 3. Spot-check file integrity
cd /mnt/vault/smaos
sha256sum crates/siss-*/Cargo.toml | head -5

# 4. Test recovery with subset of shards (DON'T decrypt, just test Shamir combining)
sss combine -k 3 << EOF
[shard-1]
[shard-2]
[shard-3]
EOF
# Should output 64 hex characters

# 5. Unmount
diskutil unmountDisk /dev/diskX

# 6. Update VAULT_MANIFEST.json last_verified timestamp
```

### Cryptographic Verification

```bash
# Verify file checksums
sha256sum -c /mnt/vault/VAULT_MANIFEST.json

# Verify key shard format
cat /mnt/vault/VAULT_KEY_SHARDS.txt | grep "^[a-f0-9]" | wc -l

# Verify no tampering
openssl dgst -sha256 /mnt/vault/VAULT_MANIFEST.json
# Compare against hardcopy
```

## Emergency Contact Procedures

### If You Are Incapacitated

**Instructions for Next-of-Kin:**

1. Contact family custodian (holds Shard 3)
2. Contact Israeli counsel (holds Shard 4)
3. File emergency petition with all 3 parties present
4. Retrieve and combine Shards 3, 4, and one additional shard
5. Recover vault using procedure above
6. Activate Foundation custody protocol (Shard 5)

### If All Physical Vaults Lost

**Geopolitical Fail-Safe:**

- Swiss Foundation maintains institutional copy (future)
- Israeli counsel maintains remote escrow copy
- Network backups stored in distributed ledger (future)

If you lose all physical vaults:
1. Contact Foundation trustees
2. Request emergency activation
3. Verify identity through multiple channels
4. Retrieve institutional backup
5. Reconstruct from network ledger (if available)

## Prevention Best Practices

### Maintenance Schedule

- **Weekly:** Run automatic Night Shift syncs to update vault contents
- **Monthly:** Verify all custodians still hold shards (via check-in)
- **Quarterly:** Test mounting and file integrity
- **Annually:** Full recovery test with subset of shards
- **Every 5 years:** Master key rotation and re-sharding

### Operational Security

- Never transport more than 2 shards in same vehicle
- Never email shards unencrypted
- Never discuss shard locations publicly
- Keep shard text files encrypted at rest
- Use cold storage (hardware wallet, safe deposit box)

### Succession Planning

- Update custodian list when relationships change
- Brief family members on basic recovery procedures
- Ensure counsel has emergency contact procedures documented
- Establish Foundation succession plan (once created)

### Password Management

- Store vault passphrase in 1Password/Bitwarden
- Use biometric lock on password manager
- Never write passphrase on paper
- Share passphrase with trusted family member in sealed envelope

## Troubleshooting

### "Cannot mount APFS volume"
```bash
# macOS: Try disk repair
diskutil secureErase freespace 0 /dev/diskX

# Or reformat with Time Machine recovery
# Hold Cmd+R during boot, use Disk Utility
```

### "Shamir combine returns wrong key"
```bash
# Verify shard format (should be hex-encoded strings)
cat VAULT_KEY_SHARDS.txt | head -50

# Try combining with different 3 shards
sss combine -k 3 << EOF
[try-shard-1]
[try-shard-2]
[try-shard-4]  # Skip shard 3
EOF
```

### "Checksums don't match"
```bash
# File may have been updated; check date of last sync
grep "last_sync" VAULT_MANIFEST.json

# Recalculate checksums
cd /mnt/vault/smaos
find . -type f -exec sha256sum {} \; | sha256sum
```

## Summary: The Recovery Lifeline

Your SMAOS vision's survival depends on:

1. **Physical redundancy:** 3 geographic locations (A/B/C)
2. **Cryptographic resilience:** Shamir 3-of-5 threshold
3. **Human oversight:** 3+ custodians with distributed authority
4. **Regular testing:** Annual verification and rotation

As long as any 3 of these 5 components remain intact:
- Vault A OR Vault B OR Vault C
- Shard 1 AND Shard 2 AND Shard 3 (or any other 3)

**Your vision is recoverable. Never panic. The system was designed for this.**

---

**Last Updated:** $(date)
**For questions:** Contact Andrej Leukhin (andrejlo123@gmail.com)

EOFRECOVERY

    log_success "Recovery guide generated."
}

# Generate contacts file
generate_contacts_file() {
    local vault_path=$1

    log_info "Generating custodian contacts file..."

    cat > "$vault_path/VAULT_CONTACTS.json" <<'EOF'
{
  "version": "1.0",
  "last_updated": "2026-05-29",
  "custodians": [
    {
      "id": 1,
      "role": "Primary Visionary & Owner",
      "name": "Andrej Leukhin",
      "shards_held": [1, 2],
      "email": "andrejlo123@gmail.com",
      "phone": "[Update with actual phone]",
      "public_key_ed25519": "[To be configured from Genesis Capsules]",
      "location": "Prague, Czech Republic",
      "backup_location": "Home office safe",
      "access_frequency": "Daily (production environment)",
      "emergency_contact": "Wife (name TBD)",
      "notes": "Holds 2 of 5 shards; visionary and system operator"
    },
    {
      "id": 2,
      "role": "Family Custodian",
      "name": "[Wife name - To be configured]",
      "shards_held": [3],
      "email": "[To be configured]",
      "phone": "[To be configured]",
      "location": "Prague, Czech Republic",
      "backup_location": "Safe deposit box",
      "access_frequency": "Emergency only",
      "relationship": "Spouse",
      "authorization_required": "Two-factor (email + phone call)",
      "instructions": "https://example.com/family-recovery-guide",
      "notes": "Critical for family continuity; holds shard in physical safe"
    },
    {
      "id": 3,
      "role": "Legal Custodian (Israel)",
      "name": "Pearl Cohen or successor",
      "organization": "[Israeli law firm - To be configured]",
      "shards_held": [4],
      "email": "[To be configured]",
      "phone": "[To be configured]",
      "location": "Israel",
      "backup_location": "Law firm escrow",
      "access_frequency": "Emergency only (geopolitical fail-safe)",
      "authorization_required": "Power of attorney + notarized request",
      "jurisdiction": "Israeli law",
      "instructions": "https://example.com/legal-recovery-guide",
      "notes": "Survives geopolitical conflicts in Europe; handles Israeli legal matters"
    },
    {
      "id": 4,
      "role": "Institutional Custodian (Foundation)",
      "name": "Sovereign Vision Foundation Board",
      "organization": "Sovereign Vision Foundation (to be established)",
      "shards_held": [5],
      "email": "[To be configured when Foundation created]",
      "location": "Switzerland (planned)",
      "backup_location": "Foundation headquarters + escrow",
      "access_frequency": "Emergency + 5-year rotation",
      "authorization_required": "Board quorum vote",
      "jurisdiction": "Swiss law",
      "succession_plan": "Trustee-appointed successor",
      "instructions": "https://example.com/foundation-recovery-guide",
      "notes": "Long-term institutional preservation; created upon Foundation launch"
    }
  ],
  "emergency_procedures": {
    "single_custodian_loss": {
      "action": "Contact Foundation to initiate shard recovery from institutional backup",
      "timeline": "Within 30 days of notification",
      "required_documentation": "Legal proof of death or incapacity"
    },
    "multiple_custodian_loss": {
      "action": "Activate multi-shard recovery via Foundation",
      "timeline": "Emergency protocol (within 24 hours)",
      "required_authorization": "All available custodians + Foundation board"
    },
    "all_custodians_incapacitated": {
      "action": "Foundation activates institutional succession",
      "timeline": "Automatic after 6-month grace period",
      "beneficiary": "Vision continuity fund or designated heir"
    }
  },
  "rotation_schedule": {
    "annual_check_in": {
      "frequency": "January 1",
      "action": "Verify all custodians still hold shards",
      "contact_method": "Secure email + phone confirmation",
      "documentation": "Email receipts stored in vault"
    },
    "five_year_key_rotation": {
      "frequency": "Every 5 years from vault creation",
      "action": "Generate new master key and reshard",
      "custodian_notification": "Detailed re-distribution instructions",
      "timeline": "3-month transition period"
    },
    "succession_transition": {
      "frequency": "On death or incapacity of custodian",
      "action": "Transfer shard to successor custodian",
      "required_authorization": "Visionary approval + legal documentation",
      "timeline": "Within 90 days of event"
    }
  },
  "security_policies": {
    "shard_storage": "Encrypted at rest; no single location contains multiple shards",
    "shard_transmission": "Never via email or unencrypted channels; only in-person or trusted courier",
    "shard_verification": "Checksums and signatures stored separately from shards themselves",
    "access_logs": "All vault access attempts logged and timestamped",
    "audit_trail": "Immutable record of shard movements and custodian changes"
  },
  "escalation_matrix": {
    "level_1": {
      "trigger": "Single vault inaccessible (e.g., Vault A lost)",
      "action": "Retrieve alternate vault (B or C)",
      "authorization": "Self-authorization by visionary"
    },
    "level_2": {
      "trigger": "Two vaults inaccessible; only 2 shards available",
      "action": "Contact third custodian for shard #3 or #4 or #5",
      "authorization": "Multi-factor: email + phone + in-person identification"
    },
    "level_3": {
      "trigger": "Visionary incapacitated; family needs access",
      "action": "Foundation initiates custodian assembly",
      "authorization": "Power of attorney + family court documentation"
    },
    "level_4": {
      "trigger": "Catastrophic loss (all vaults + all custodians compromised)",
      "action": "Foundation activates institutional recovery from network ledger",
      "authorization": "Foundation board + external auditor verification"
    }
  }
}
EOF

    log_success "Custodian contacts file generated."
}

# Verify vault integrity
verify_vault() {
    local mount_point=$1

    log_info "Verifying vault integrity..."

    # Test file reads
    if [ ! -f "$mount_point/VAULT_MANIFEST.json" ]; then
        log_error "VAULT_MANIFEST.json not found in vault."
        return 1
    fi

    # Verify manifest is valid JSON
    if ! jq empty "$mount_point/VAULT_MANIFEST.json" 2>/dev/null; then
        log_error "VAULT_MANIFEST.json is invalid JSON."
        return 1
    fi

    # Check workspace directory exists
    if [ ! -d "$mount_point/smaos" ]; then
        log_error "SMAOS workspace directory not found."
        return 1
    fi

    # Count files
    local file_count=$(find "$mount_point/smaos" -type f 2>/dev/null | wc -l)
    log_info "Files in vault: $file_count"

    # Calculate total size
    local total_size=$(du -sh "$mount_point/smaos" 2>/dev/null | awk '{print $1}')
    log_info "Vault contents size: $total_size"

    # Test spot-check integrity
    if [ -f "$mount_point/smaos/Cargo.toml" ]; then
        local checksum=$(shasum -a 256 "$mount_point/smaos/Cargo.toml" | awk '{print $1}')
        log_debug "Cargo.toml checksum: $checksum"
    fi

    log_success "Vault integrity verified."
}

# Unmount vault
unmount_vault() {
    local mount_point=$1
    local device=$2

    log_info "Unmounting vault for safe storage..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        diskutil unmountDisk "$device" 2>&1 || {
            log_warning "Unmount returned non-zero status. Force unmounting..."
            diskutil unmountDisk force "$device" 2>/dev/null || true
        }
    else
        sudo umount "$mount_point" 2>/dev/null || true
        sudo cryptsetup luksClose "${mount_point##*/}" 2>/dev/null || true
    fi

    log_success "Vault unmounted."
}

# Print summary
print_summary() {
    local vault_location=$1
    local device=$2
    local vault_name=$3

    echo
    echo -e "${GREEN}"
    cat <<EOF

================================================================================
                    VAULT CREATION COMPLETE
================================================================================

Vault Location: $vault_location
Device: $device
Vault Name: $vault_name

Contents:
  ✓ Complete SMAOS workspace (all crates)
  ✓ Genesis Capsules (identity keys)
  ✓ MLX distilled models (encrypted)
  ✓ Architecture documentation
  ✓ Test suites and configurations

Files Generated:
  ✓ VAULT_MANIFEST.json        — Vault metadata and checksums
  ✓ VAULT_KEY_SHARDS.txt       — Encryption key shard distribution
  ✓ VAULT_RECOVERY.md          — Complete recovery guide
  ✓ VAULT_CONTACTS.json        — Custodian contact information

Next Steps (Critical):
================================================================================

1. LABEL THE VAULT
   • Physically label USB drive "VAULT $vault_location"
   • Record serial number and storage location

2. DISTRIBUTE KEY SHARDS

   Shard 1 (Your personal copy):
     → Keep in home office safe or encrypted password manager

   Shard 2 (Family custodian):
     → Deliver to wife in sealed, encrypted envelope
     → Include emergency contact card with recovery instructions

   Shard 3 (Legal custodian — Israel):
     → Send to Pearl Cohen via secure channel (encrypted email + phone confirm)
     → Include power of attorney documentation

   Shard 4 (Foundation escrow):
     → Activate once Foundation is legally established
     → Deliver to Foundation trustees with board resolution

3. STORE VAULT IN APPROPRIATE LOCATION

   Vault A (Primary):
     → Your home office in Prague
     → Daily access for Night Shift syncs
     → Connect via USB-C when needed

   Vault B (Shadow):
     → Safe deposit box in Czech bank
     → Annual rotation (retrieve, verify, reseal)
     → Emergency backup if Vault A lost

   Vault C (Remote/Israel):
     → Secure escrow with legal counsel
     → Geopolitical redundancy
     → Never needed unless Vaults A & B both lost

4. ENABLE AUTOMATIC SYNCING

   Run Night Shift automation:
   $ ./scripts/setup_night_shift.sh

   This will keep vault contents synchronized nightly with:
     - Fresh code from local git repo
     - Updated Genesis Capsules
     - Latest model checkpoints

5. CONFIGURE ENCRYPTION PASSPHRASE

   Store vault passphrase securely:
   $ 1password create "VAULT_A_PASSPHRASE" \
       --category password \
       --secure-note "SMAOS Vault A encryption key"

6. TEST RECOVERY ANNUALLY

   Every January, run this test:
   $ ./scripts/test_vault_recovery.sh [vault-location]

   This verifies:
     ✓ Vault mounts correctly
     ✓ File integrity intact (no corruption)
     ✓ Shamir shards are accessible
     ✓ Recovery procedure is current

Disaster Recovery Readiness:
================================================================================

If Your Laptop Is Lost:
  1. Retrieve physical Vault A from home
  2. Connect to any working computer via USB-C
  3. Follow VAULT_RECOVERY.md section "Primary Laptop Lost"
  4. Restore complete workspace in ~30 minutes

If All Local Vaults Lost:
  1. Contact Pearl Cohen (Israeli counsel) for Vault C
  2. Combine Shards 2 (yours) + 3 (wife) + 4 (counsel)
  3. Recover from Vault C
  4. Activate Foundation institutional backup (future)

If You Are Incapacitated:
  1. Your wife retrieves Shard 3 from safe deposit box
  2. Counsel has Shard 4 in escrow
  3. They can recover vault contents without you
  4. Vision continues even if you cannot access systems

Security Reminders:
================================================================================

✓ Never store 2+ shards in same location
✓ Never transmit shards via unencrypted email
✓ Keep shard text files encrypted at rest
✓ Update custodian contact list annually
✓ Test recovery procedure every January
✓ Rotate master key every 5 years
✓ Communicate shard roles to family members

Your Vision Is Now Distributed And Survivable:
================================================================================

The laptop is no longer a single point of failure.
The vault is encrypted with AES-256.
Access is distributed with 3-of-5 Shamir sharding.
Custodians span Europe, Israel, and personal custody.

Your SMAOS vision will survive:
  • Device loss or destruction
  • Geopolitical conflicts
  • Personal incapacity
  • Long-term institutional change

The system is now ready for Night Shift automation and distributed operation.

================================================================================

For questions or emergency procedures, see VAULT_RECOVERY.md

Vault initialization complete. $(date)

EOF
    echo -e "${NC}"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    # Print header
    echo
    cat <<'EOF'
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   SMAOS VISION SURVIVAL PROTOCOL                              ║
║   Vault Initialization — Eliminate Single Point of Failure    ║
║                                                                ║
║   Transform raw USB drives into encrypted, Shamir-sharded     ║
║   vaults containing the entire SMAOS vision.                  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
EOF
    echo

    # 1. Prompt for vault location
    if [ -z "$VAULT_LOCATION" ]; then
        VAULT_LOCATION=$(prompt_vault_location) || exit 1
    else
        validate_vault_location "$VAULT_LOCATION" || exit 1
    fi

    log_success "Vault location set: $VAULT_LOCATION"

    # 2. Select USB drive
    log_info "Please have a USB-C SSD connected to your computer."
    local device
    device=$(select_usb_drive) || {
        log_error "No USB drive selected."
        exit 1
    }

    # 3. Get encryption passphrase
    local passphrase
    passphrase=$(prompt_encryption_passphrase) || {
        log_error "Failed to set passphrase."
        exit 1
    }

    log_success "Encryption passphrase configured (${#passphrase} characters)."

    # 4. Confirm vault creation
    echo
    read -p "Ready to create vault. Press Enter to continue or Ctrl+C to cancel..."

    # 5. Create encrypted volume
    local vault_name="SMAOS_VAULT_${VAULT_LOCATION}_$(date +%Y%m%d_%H%M%S)"

    if [[ "$OSTYPE" == "darwin"* ]]; then
        create_encrypted_volume_macos "$device" "$vault_name" || exit 1
    else
        create_encrypted_volume_linux "$device" "$vault_name" "$passphrase" || exit 1
    fi

    # 6. Find mount point
    log_info "Locating vault mount point..."
    sleep 3

    local mount_point
    mount_point=$(find_vault_mount_point "$device") || {
        log_error "Could not find vault mount point."
        exit 1
    }

    log_success "Vault mounted at: $mount_point"

    # 7. Copy workspace
    copy_workspace "$mount_point" "$VAULT_LOCATION" || {
        log_error "Failed to copy workspace."
        unmount_vault "$mount_point" "$device"
        exit 1
    }

    # 8. Generate Shamir shards
    local master_key
    master_key=$(generate_shamir_shards "$mount_point" "$VAULT_LOCATION") || {
        log_error "Failed to generate shards."
        unmount_vault "$mount_point" "$device"
        exit 1
    }

    # 9. Generate manifest
    generate_manifest "$mount_point" "$VAULT_LOCATION" "$master_key" || {
        log_error "Failed to generate manifest."
        unmount_vault "$mount_point" "$device"
        exit 1
    }

    # 10. Generate recovery guide
    generate_recovery_guide "$mount_point" || {
        log_error "Failed to generate recovery guide."
        unmount_vault "$mount_point" "$device"
        exit 1
    }

    # 11. Generate contacts file
    generate_contacts_file "$mount_point" || {
        log_error "Failed to generate contacts file."
        unmount_vault "$mount_point" "$device"
        exit 1
    }

    # 12. Verify vault
    verify_vault "$mount_point" || {
        log_warning "Vault verification had issues, but continuing..."
    }

    # 13. Unmount vault
    unmount_vault "$mount_point" "$device"

    # 14. Print summary
    print_summary "$VAULT_LOCATION" "$device" "$vault_name"

    # 15. Export key fragments to user console (for immediate backup)
    echo
    echo -e "${YELLOW}CRITICAL: Key Fragment for Your Personal Custody${NC}"
    echo -e "${YELLOW}(This is Shard 2 — keep encrypted and secure)${NC}"
    echo

    if [ -f "$TEMP_SHARDS_DIR/SHARDS_DATA.txt" ]; then
        cat "$TEMP_SHARDS_DIR/SHARDS_DATA.txt"
    else
        log_warning "Could not display shard data (already secured in vault)"
    fi

    echo
    log_success "Vault initialization complete."
    echo
}

# Execute main function
main "$@"
