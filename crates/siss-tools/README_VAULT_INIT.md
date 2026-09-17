# Vault Initialization Script — Vision Survival Protocol

## Overview

`vault_init.sh` transforms raw USB-C SSDs into encrypted, Shamir-sharded vaults containing the complete SMAOS vision. This is the **physical foundation** of vision resilience — it eliminates the laptop as a single point of failure.

## The Problem

Your laptop is currently a **single point of failure**. If it's lost, destroyed, or stolen:
- Complete vision loss
- All identity keys compromised or gone
- Months of work erased
- Zero recovery path

## The Solution

Create **3 geographically distributed, encrypted vaults (A/B/C)** that:
- Are **encrypted with AES-256-GCM** (military-grade)
- Use **Shamir Secret Sharing (3-of-5 threshold)** for key distribution
- Span **Europe (home + safe deposit) + Israel (geopolitical fail-safe)**
- Can be **recovered independently** — no single custodian has unilateral control
- Are **automatically synchronized** via Night Shift nightly

If your laptop is lost, you can recover the entire vision from any vault in **~30 minutes**.

If all physical vaults are lost, you can recover from **any combination of 3 key shards** held by family, counsel, and Foundation.

## Architecture

### Vault Locations

| Vault | Location | Purpose | Access |
|-------|----------|---------|--------|
| **A** | Home office (Prague) | Primary production | Daily (Night Shift syncs) |
| **B** | Safe deposit box (Czech bank) | Shadow backup | Annual rotation |
| **C** | Escrow (Israel, counsel) | Geopolitical fail-safe | Emergency only |

### Encryption Model

```
Master Key (256-bit AES)
    ↓
Shamir Secret Sharing (3-of-5)
    ├─ Shard 1: Vault A (encrypted QR code)
    ├─ Shard 2: Your personal safe (1Password, Bitwarden)
    ├─ Shard 3: Family member (wife)
    ├─ Shard 4: Legal custodian (Israel counsel)
    └─ Shard 5: Foundation escrow (future)

To recover: Combine ANY 3 of 5 shards → Decrypt vault → Restore workspace
```

### Key Features

✓ **Hardware Detection** — Auto-detects connected USB-C SSDs  
✓ **Encryption** — AES-256-GCM on APFS (macOS) or LUKS (Linux)  
✓ **Workspace Copy** — Entire SMAOS repo + Genesis Capsules + Models  
✓ **Shamir Sharding** — Distribute decryption key across 5 custodians  
✓ **Manifest Generation** — UUID, checksums, metadata for verification  
✓ **Recovery Guide** — Step-by-step procedures for 4 emergency scenarios  
✓ **Contacts Registry** — Custodian roles, contact info, authorization rules  
✓ **Integrity Verification** — SHA-256 spot-checks, file count validation  
✓ **Cross-Platform** — macOS and Linux support  

## Usage

### Prerequisites

- USB-C SSD (minimum 500GB recommended)
- USB-C connection capability
- Root/admin access (encryption requires elevated privileges)
- 30–60 minutes for initial setup

### Basic Workflow

#### Step 1: Create Vault A (Primary)

```bash
cd ./crates/siss-tools

# Run with location A (primary)
./vault_init.sh A
```

The script will:
1. Detect connected USB-C SSDs
2. Prompt you to select a drive
3. Request encryption passphrase (min 32 characters)
4. Create encrypted APFS volume
5. Copy entire SMAOS workspace (~5–10 minutes)
6. Generate Shamir shards (3-of-5)
7. Create VAULT_MANIFEST.json, recovery guides, contacts file
8. Verify integrity
9. Unmount vault for safe storage

#### Step 2: Create Vault B (Shadow)

Repeat with a second USB-C SSD:

```bash
./vault_init.sh B
```

Store in safe deposit box with the bank.

#### Step 3: Create Vault C (Remote)

Repeat with a third USB-C SSD:

```bash
./vault_init.sh C
```

Deliver to Israeli counsel (Pearl Cohen) for escrow storage.

### Step-by-Step Walkthrough

**Console Output Example:**

```
╔════════════════════════════════════════════════════════════════╗
║   SMAOS VISION SURVIVAL PROTOCOL                              ║
║   Vault Initialization — Eliminate Single Point of Failure    ║
╚════════════════════════════════════════════════════════════════╝

Vault Locations:
  A — Primary (your home office, Prague)
  B — Shadow (safe deposit box, Czech Republic)
  C — Remote (escrow/counsel, Israel)

Enter vault location (A/B/C): A

[INFO] Vault location set: A
[INFO] Please have a USB-C SSD connected to your computer.
[INFO] Detecting USB-C SSDs...

Available USB-C SSDs:
 1. Samsung T9 (USB 3.2)        | Size: 2TB            | Protocol: USB
 2. Crucial X9 Pro (USB-C SSD)  | Size: 1TB            | Protocol: USB

Select drive number: 1

[INFO] Selected: /dev/disk2 — Samsung T9 (2TB)

[WARNING] Choose a strong passphrase (minimum 32 characters, 
mixed case, numbers, symbols).

Enter encryption passphrase: **[hidden input]**
Confirm passphrase: **[hidden input]**

[SUCCESS] Encryption passphrase configured (48 characters).

Ready to create vault. Press Enter to continue or Ctrl+C to cancel...

[INFO] Creating encrypted APFS volume on /dev/disk2...
[SUCCESS] Encrypted APFS volume created: SMAOS_VAULT_A_20260529_140530

[INFO] Locating vault mount point...
[SUCCESS] Vault mounted at: /Volumes/SMAOS_VAULT_A_20260529_140530

[INFO] Copying SMAOS workspace to vault (this may take several minutes)...

... [5–10 minute copy with progress] ...

[SUCCESS] Workspace copied to vault.

[INFO] Generating Shamir Secret Sharing (3-of-5) for vault encryption...
[SUCCESS] Shamir shards generated and stored in vault.

[INFO] Generating vault manifest...
[SUCCESS] Vault manifest generated.

[INFO] Generating emergency recovery guide...
[SUCCESS] Recovery guide generated.

[INFO] Generating custodian contacts file...
[SUCCESS] Custodian contacts file generated.

[INFO] Verifying vault integrity...
[INFO] Files in vault: 15,847
[INFO] Vault contents size: 4.2GB
[SUCCESS] Vault integrity verified.

[INFO] Unmounting vault for safe storage...
[SUCCESS] Vault unmounted.

================================================================================
                    VAULT CREATION COMPLETE
================================================================================

Vault Location: A
Device: /dev/disk2
Vault Name: SMAOS_VAULT_A_20260529_140530

Next Steps (Critical):
================================================================================

1. LABEL THE VAULT
   • Physically label USB drive "VAULT A"
   • Record serial number

2. DISTRIBUTE KEY SHARDS
   Shard 1: Keep in home office safe
   Shard 2: Give to wife in sealed envelope
   Shard 3: Send to Pearl Cohen (encrypted email)
   Shard 4: [Future Foundation]

3. STORE VAULT
   Vault A: Home office in Prague (daily access)
   ...

[SUCCESS] Vault initialization complete.
```

## Generated Files

After running `vault_init.sh`, the vault contains:

### Structure

```
Vault Root (encrypted USB-C SSD)
├── VAULT_MANIFEST.json
│   └─ UUID, creation date, checksums, metadata
│
├── VAULT_KEY_SHARDS.txt
│   └─ Shamir shard distribution instructions + contacts
│
├── VAULT_RECOVERY.md
│   ├─ Emergency Scenario 1: Laptop Lost
│   ├─ Emergency Scenario 2: Vault A Lost
│   ├─ Emergency Scenario 3: Multiple Vaults Lost
│   ├─ Emergency Scenario 4: Shards Compromised
│   ├─ Technical Deep Dive (Shamir math)
│   ├─ Annual Verification Procedures
│   └─ Troubleshooting Guide
│
├── VAULT_CONTACTS.json
│   ├─ Custodian roles and contact info
│   ├─ Emergency procedures and escalation matrix
│   ├─ Rotation schedule (annual check-in, 5-year key rotation)
│   └─ Succession planning guidelines
│
└── smaos/
    ├── crates/
    │   ├── siss-*/
    │   └── [All SISS system crates]
    │
    ├── docs/
    ├── .claude/
    │   └── private/
    │       └── [Genesis Capsules — identity keys]
    │
    ├── Cargo.toml, Cargo.lock
    └── [Complete SMAOS workspace]
```

### Key Files Explained

**VAULT_MANIFEST.json**
- Vault UUID and location
- Creation timestamp
- Contents list (crates, models, keys)
- Encryption algorithm and Shamir configuration
- File count, total size, checksums
- Last sync date
- Next annual review date

**VAULT_KEY_SHARDS.txt**
- Distribution protocol for 5 shards
- Custodian assignments (you, wife, counsel, Foundation)
- Recovery procedure (sss-cli combine command)
- Contact matrix
- Security warnings
- Audit trail

**VAULT_RECOVERY.md**
- Step-by-step recovery for 4 scenarios
- Technical Shamir Secret Sharing explanation
- Annual verification procedures
- Emergency contact flow
- Troubleshooting guide

**VAULT_CONTACTS.json**
- Custodian roles and email/phone
- Authorization rules (2FA, multi-signer)
- Rotation schedules
- Succession plan
- Escalation matrix (levels 1–4)

## Emergency Procedures

### Scenario 1: Laptop Lost/Destroyed

**Time to recovery: ~30 minutes**

```bash
# 1. Retrieve physical Vault A from home
# 2. Connect to any working computer via USB-C
# 3. Combine 3 key shards (you have 2; get 1 from wife/counsel)
sss combine -k 3 << EOF
[shard-1]
[shard-2]
[shard-3]
EOF

# 4. Decrypt and mount vault
diskutil mount /Volumes/SMAOS_VAULT_A_*

# 5. Copy workspace back to computer
cp -r /Volumes/SMAOS_VAULT_A_*/smaos ~/Documents/SovereignNexus

# 6. Rebuild and verify
cd ~/Documents/SovereignNexus
cargo build
cargo test

# Done. Vision restored.
```

### Scenario 2: Vault A Lost/Corrupted

**Time to recovery: 2–24 hours (depends on safe deposit box access)**

```bash
# 1. Retrieve Vault B from safe deposit box
# 2. Follow same recovery procedure as Scenario 1
# 3. Update VAULT_MANIFEST.json with new Vault A details
```

### Scenario 3: Multiple Vaults Lost (A & B)

**Time to recovery: 1–7 days (depends on geopolitical situation)**

```bash
# 1. Contact Pearl Cohen (Israeli counsel) for Vault C
# 2. Provide proof of identity + notarized request
# 3. Retrieve Vault C from escrow
# 4. Follow standard recovery (need 3 of 5 shards)
# 5. Activate Foundation institutional backup (future)
```

### Scenario 4: Key Shards Exposed

```bash
# If fewer than 3 shards remain accessible:
# 1. Activate Foundation emergency protocol
# 2. Rotate master key with existing vault access
# 3. Generate new shards and redistribute

./vault_init.sh A  # Reinitialize with fresh shards
```

## Shamir Secret Sharing — Technical Details

The script uses **3-of-5 Shamir Secret Sharing** to distribute vault access:

### Why 3-of-5?

| Property | Benefit |
|----------|---------|
| **Threshold = 3** | Survives loss of any 2 shards |
| **Total = 5** | Distributes authority (no single custodian has keys) |
| **Geopolitical spread** | Europe + Israel + personal custody |
| **Mathematical security** | Mathematically impossible to recover key with <3 shards |

### Shard Distribution

```
Shard 1 + 2: Your personal custody (2 locations)
  → Shard 1: Encrypted within Vault A itself
  → Shard 2: Personal safe (1Password, Bitwarden, hardware wallet)

Shard 3: Family custodian
  → Wife or trusted family member
  → Safe deposit box or home safe

Shard 4: Legal custodian
  → Pearl Cohen (Israeli counsel)
  → Law firm escrow

Shard 5: Institutional custodian
  → Swiss Foundation (future)
  → Long-term institutional preservation
```

### Recovery Example

If your laptop fails and you need Vault A:

```bash
# Gather 3 shards (you have Shards 1+2, get Shard 3 from wife)
cat > /tmp/my_shards.txt << EOF
[your-shard-1-value]
[your-shard-2-value]
[wifes-shard-3-value]
EOF

# Combine using Shamir Secret Sharing
sss combine -k 3 < /tmp/my_shards.txt > /tmp/master_key.txt

# Use key to mount encrypted vault
# [Standard mount procedure from VAULT_RECOVERY.md]

# Destroy shard data from memory
shred -u /tmp/my_shards.txt /tmp/master_key.txt
```

## Maintenance Schedule

### Weekly
- Automatic Night Shift syncs update vault contents
- No manual action required

### Monthly
- Verify all custodians still hold shards (quick email check-in)

### Annually (January)
- Full recovery test (mount vault, verify integrity, test Shamir combine)
- Update custodian contact information
- Verify vault checksums match manifest

### Every 5 Years
- Master key rotation (generate new key, reshard, redistribute)
- Custodian succession updates (if roles changed)

## Installation & Configuration

### Prerequisites

**macOS:**
- Xcode Command Line Tools (for diskutil)
- openssl (for encryption)
- sss-cli (optional, for production Shamir sharing)
  ```bash
  brew install ssss  # or equivalent
  ```

**Linux:**
- cryptsetup (for LUKS encryption)
- openssl
- rsync (for efficient copying)
  ```bash
  sudo apt install cryptsetup openssl rsync
  ```

### Installation

```bash
# Clone or navigate to repo
cd ./crates/siss-tools

# Make script executable
chmod +x vault_init.sh

# Test script can run
./vault_init.sh --help  # Not implemented, but no errors
```

### First Run

```bash
# Create Vault A (primary, home office)
./vault_init.sh A

# Follow interactive prompts
# ~ 30 minutes total
```

## Security Best Practices

### Do's

✓ **Use strong passphrases** — Minimum 32 characters, mixed case + numbers + symbols  
✓ **Store passphrase in encrypted password manager** — 1Password, Bitwarden, KeePass  
✓ **Never store multiple shards in same location** — Defeats purpose of distribution  
✓ **Test recovery annually** — Ensure procedures still work  
✓ **Communicate shard roles to custodians** — Family/counsel should know what they hold  
✓ **Update vault contents weekly** — Night Shift automation handles this  
✓ **Rotate master key every 5 years** — Re-shard and redistribute  

### Don'ts

✗ **Never email shards unencrypted** — Always use encrypted channels  
✗ **Never write passphrase on paper** — Keep in password manager only  
✗ **Never leave vault unattended in public** — Always secure physically  
✗ **Never attempt to decrypt vault on untrusted computer** — Use only your own machine  
✗ **Never share shard distribution matrix** — Keep custodian list confidential  
✗ **Never skip annual verification** — Small issues compound over time  

## Troubleshooting

### Issue: "No USB drives detected"

```bash
# Ensure USB-C SSD is connected
# Check if detected by system:
# macOS:
diskutil list external physical

# Linux:
lsblk | grep -i usb
```

### Issue: "Failed to create encrypted APFS volume"

```bash
# macOS: Try unmounting and force-erasing first
diskutil unmountDisk force /dev/diskX
diskutil secureErase freespace 0 /dev/diskX

# Then try vault_init.sh again
```

### Issue: "Passphrase too weak"

- Minimum 32 characters required
- Must include: uppercase, lowercase, numbers, symbols
- Example: `MyVault2026!SovereIgnNexus#Alpha1`

### Issue: "Cannot mount vault after creation"

```bash
# macOS: Try manually mounting
diskutil mount /dev/diskX

# If that fails, vault may be corrupted
# Check APFS container:
diskutil apfs list

# Recovery: Recreate vault on same SSD
./vault_init.sh A
```

### Issue: "Shamir combine returns wrong key"

```bash
# Verify shard format (should be hex strings)
cat VAULT_MANIFEST.json | grep -A 20 "key_distribution"

# Try different combination of 3 shards
# (any 3 of 5 should work)
```

## Integration with Night Shift

Once vault is created, enable automatic syncing:

```bash
# Navigate to siss-night-cycle
cd ./crates/siss-night-cycle

# Configure vault sync
./setup_night_shift.sh --vault A --frequency nightly

# Verify sync is active
./scripts/status_night_shift.sh
```

Every night, Night Shift will:
1. Check for changes in local repo
2. Sync fresh code to Vault A
3. Update Genesis Capsules if changed
4. Recalculate and verify checksums
5. Log sync results

## Next Steps

### Immediate (Today)

- [ ] Create Vault A (primary)
- [ ] Label USB drive "VAULT A"
- [ ] Store in home office
- [ ] Record passphrase in 1Password

### This Week

- [ ] Create Vault B (shadow)
- [ ] Store in safe deposit box
- [ ] Create Vault C (remote)
- [ ] Deliver to Israeli counsel with instructions

### This Month

- [ ] Distribute key shards to custodians
  - [ ] Give Shard 3 to wife (sealed envelope)
  - [ ] Send Shard 4 to Pearl Cohen (encrypted email)
  - [ ] Reserve Shard 5 for Foundation (future)
  
- [ ] Brief each custodian on their role
- [ ] Enable Night Shift vault sync
- [ ] Test recovery procedure with Vault B

### Ongoing

- [ ] Monthly: Verify custodians still hold shards
- [ ] Quarterly: Mount vault and verify integrity
- [ ] Annually: Full recovery test + key rotation
- [ ] Every 5 years: Master key rotation + re-sharding

## FAQ

**Q: What if I lose all 5 shards?**
A: Vault is unrecoverable. Prevent: Store Shard 1 & 2 with you, distribute 3–5 to others.

**Q: What if all custodians die?**
A: Foundation trustee succession activates (future). For now, brief a successor executor.

**Q: Can I recover vault without internet?**
A: Yes. Vault decryption is purely cryptographic (no internet needed). Shamir combining is offline.

**Q: How do I update vault contents?**
A: Night Shift automation syncs nightly. Manual update: Re-create vault or use rsync.

**Q: What if I forget the encryption passphrase?**
A: Cannot recover. Passphrase is not stored. **Store in password manager immediately.**

**Q: Can I use a cheaper USB drive?**
A: Yes, but 500GB+ recommended. Cheaper drives may be slower or less reliable.

**Q: Is AES-256-GCM breakable?**
A: Not known to be breakable (256-bit key = 2^256 brute-force attempts). Safe for 20+ years.

**Q: What if law enforcement demands the vault?**
A: You can surrender the physical USB, but decryption key is with multiple custodians. No single person can comply.

## References

- **Shamir Secret Sharing:** https://en.wikipedia.org/wiki/Shamir%27s_Secret_Sharing
- **AES-256-GCM:** NIST FIPS 197, RFC 5116
- **APFS Encryption:** Apple Platform Security, Chapter 2
- **LUKS:** Linux Unified Key Setup 2.0 Specification

## Support & Contact

For questions or issues:
- **Author:** Andrej Leukhin (andrejlo123@gmail.com)
- **Emergency Recovery:** See VAULT_RECOVERY.md
- **Custodian Instructions:** See VAULT_KEY_SHARDS.txt
- **Contact Matrix:** See VAULT_CONTACTS.json (generated in vault)

---

**Your vision is now distributed and survivable. The laptop is no longer a single point of failure.**

Created: May 29, 2026
Last Updated: May 29, 2026
