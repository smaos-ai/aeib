# Vault Initialization — Execution Checklist

## Pre-Execution Checklist

### Hardware Preparation

- [ ] **Obtain 3 USB-C SSDs** (500GB+ each, recommended: Samsung T9, Crucial X9 Pro)
  - [ ] SSD 1 labeled for Vault A
  - [ ] SSD 2 labeled for Vault B
  - [ ] SSD 3 labeled for Vault C
  
- [ ] **Test USB-C connections**
  - [ ] At least one USB-C SSD enclosure available
  - [ ] USB-C adapter for backup (if using hub)
  - [ ] All drives recognized by system (`diskutil list`)

- [ ] **Prepare workspace**
  - [ ] Quiet, uninterrupted environment (30–60 min per vault)
  - [ ] Working computer with admin access
  - [ ] Internet connection (optional, for sss-cli installation)

### Information Preparation

- [ ] **Custodian contact list prepared**
  - [ ] Wife name, phone, email
  - [ ] Pearl Cohen (Israeli counsel) contact info
  - [ ] Foundation trustees (if established)
  
- [ ] **Create encryption passphrases** (store in 1Password immediately after)
  - [ ] Vault A passphrase: ________________
  - [ ] Vault B passphrase: ________________
  - [ ] Vault C passphrase: ________________
  
  **Requirements:** Minimum 32 characters, mixed case + numbers + symbols
  
- [ ] **Prepare recovery contact emergency card**
  - Printing template in `VAULT_RECOVERY_CARD.txt` (optional)

### Software Installation (macOS)

- [ ] **Xcode Command Line Tools**
  ```bash
  xcode-select --install  # If not already installed
  ```

- [ ] **openssl** (usually pre-installed)
  ```bash
  openssl version  # Should output: OpenSSL 1.X.X or 3.X.X
  ```

- [ ] **sss-cli** (optional but recommended)
  ```bash
  brew install ssss
  sss --version
  ```

### Software Installation (Linux)

- [ ] **Required packages**
  ```bash
  sudo apt update
  sudo apt install cryptsetup openssl rsync
  ```

- [ ] **sss-cli** (optional)
  ```bash
  sudo apt install ssss
  sss --version
  ```

---

## Execution Checklist — Vault A (Primary)

### Pre-Execution

- [ ] USB-C SSD connected and recognized
- [ ] System unlocked and ready (no sleep timeout)
- [ ] No other USB drives connected (to avoid confusion)
- [ ] Terminal window open and ready

### Create Vault A

```bash
cd ./crates/siss-tools
./vault_init.sh A
```

During execution:

- [ ] **Script detects USB drive** — Select correct drive from list
- [ ] **Encrypt passphrase prompt** — Enter strong passphrase (write nothing down)
- [ ] **Confirm to proceed** — Press Enter to begin encryption
- [ ] **Workspace copy** (5–10 minutes) — Watch progress or step away
- [ ] **Shamir shard generation** — Shards are generated and displayed
- [ ] **Manifest & recovery guides generated** — On-screen confirmation
- [ ] **Vault integrity verified** — File count and size confirmed
- [ ] **Vault unmounted** — Safe for physical storage

### Post-Creation

- [ ] **Vault manifest reviewed**
  ```bash
  # On the vault (when mounted), verify manifest exists:
  cat /Volumes/SMAOS_VAULT_A_*/VAULT_MANIFEST.json | jq .
  ```

- [ ] **Passphrase stored securely**
  ```bash
  # Open 1Password / Bitwarden
  # Create new entry: "SMAOS Vault A Passphrase"
  # Paste strong passphrase
  # Save and lock password manager
  ```

- [ ] **USB drive physically labeled**
  - [ ] Label: "VAULT A — SMAOS Primary (Prague)"
  - [ ] Date: May 29, 2026
  - [ ] Serial number recorded: ________________

- [ ] **Vault A stored in appropriate location**
  - [ ] Location: Home office (Prague)
  - [ ] Storage: Encrypted drawer or safe
  - [ ] Access: Daily (for Night Shift syncs)

- [ ] **Shard 1 (Your copy) secured**
  - [ ] Location: Vault A itself (encrypted within vault)
  - [ ] Also keep in: Personal safe or hardware wallet
  - [ ] Backup: 1Password secure note

- [ ] **Key fragments exported and saved**
  - [ ] Shard 2 (Your backup) — Save to encrypted file:
    ```bash
    # Create secure note in 1Password with shard value
    # OR store in encrypted file with strong passphrase
    ```

---

## Execution Checklist — Vault B (Shadow)

### Pre-Execution

- [ ] **Second USB-C SSD connected**
- [ ] System ready (same as Vault A)
- [ ] Vault A successfully created (verify with recovery test first)

### Create Vault B

```bash
cd ./crates/siss-tools
./vault_init.sh B
```

Same execution flow as Vault A (estimated 30 minutes)

### Post-Creation

- [ ] **Vault manifest reviewed** (verify different UUID)
- [ ] **Passphrase stored** (different passphrase from Vault A)
- [ ] **USB drive labeled**
  - [ ] Label: "VAULT B — SMAOS Shadow (Czech Safe Deposit)"
  - [ ] Date: May 29, 2026
  - [ ] Serial number: ________________

- [ ] **Vault B stored in safe deposit box**
  - [ ] Bank: [Name of Czech bank]
  - [ ] Box number: ________________
  - [ ] Box key stored with you
  - [ ] Bank manager briefed (optional): Name: ________________

- [ ] **Access procedure documented**
  - [ ] Bank hours and location
  - [ ] Identification requirements
  - [ ] Emergency contact at bank

---

## Execution Checklist — Vault C (Remote)

### Pre-Execution

- [ ] **Third USB-C SSD connected**
- [ ] **Coordination with Israeli counsel**
  - [ ] Pearl Cohen's availability confirmed
  - [ ] Secure delivery method arranged
  - [ ] Contact info: ________________

### Create Vault C

```bash
cd ./crates/siss-tools
./vault_init.sh C
```

Same execution flow (30 minutes)

### Post-Creation & Delivery

- [ ] **Vault manifest reviewed** (verify third UUID)
- [ ] **Passphrase stored** (create separate password entry)
- [ ] **USB drive labeled**
  - [ ] Label: "VAULT C — SMAOS Remote (Israel Escrow)"
  - [ ] Date: May 29, 2026
  - [ ] Serial number: ________________

- [ ] **Secure delivery to Pearl Cohen**
  - [ ] Package encrypted (if shipping)
  - [ ] Tracking number: ________________
  - [ ] Delivery confirmed: Date: ________

- [ ] **Counsel briefed on procedures**
  - [ ] Escrow agreement signed
  - [ ] Contact info updated in counsel's records
  - [ ] Emergency procedure documented

---

## Shard Distribution Checklist

### Shard 1 (Your Primary Copy)
- [ ] Stored within Vault A itself (encrypted)
- [ ] Backup copy in: Personal safe / Hardware wallet
- [ ] Backup copy in: 1Password secure note
- [ ] Recovery procedure understood by you

### Shard 2 (Your Secondary Copy)
- [ ] Location: 1Password / Bitwarden
- [ ] Entry name: "SMAOS Vault — Key Shard 2 (Personal)"
- [ ] Marked as: "Emergency recovery — keep encrypted"
- [ ] Also backed up in: [Specify secondary location]

### Shard 3 (Family Custodian)
- [ ] Recipient: Wife [Name: ________________]
- [ ] Delivery method: Sealed, encrypted envelope
- [ ] Delivery date: ________________
- [ ] Confirmation received: Date: ________

**Delivery packet includes:**
- [ ] Shard 3 (printed or written)
- [ ] VAULT_RECOVERY_CARD.txt (instruction summary)
- [ ] "How to Contact Me" card
- [ ] Emergency hotline number (optional)
- [ ] Sealed and dated envelope

### Shard 4 (Legal Custodian)
- [ ] Recipient: Pearl Cohen (Israeli counsel)
- [ ] Organization: [Law firm name]
- [ ] Contact: [Email / Phone]
- [ ] Delivery method: Encrypted email + phone confirmation
- [ ] Delivery date: ________________
- [ ] Confirmation received: Date: ________

**Delivery includes:**
- [ ] Shard 4 (in encrypted PDF/encrypted email)
- [ ] VAULT_RECOVERY_CARD.txt (in encrypted attachment)
- [ ] Escrow agreement (if applicable)
- [ ] Power of attorney documentation (optional)

### Shard 5 (Foundation — Future)
- [ ] Status: Reserved for Foundation trustees
- [ ] Created and stored in Vault C
- [ ] Foundation established: Date: ________
- [ ] Delivered to Foundation: Date: ________

---

## Initial Recovery Test Checklist

**When:** Within 1 week of vault creation  
**Purpose:** Verify vaults can be mounted and recovered without data loss

### Test with Vault B

1. [ ] **Retrieve Vault B from safe deposit box**
   - [ ] Appointment made: Date: ________
   - [ ] Box opened and contents verified
   - [ ] Serial number matches

2. [ ] **Mount vault on computer**
   ```bash
   diskutil list external  # macOS
   diskutil mount /dev/diskX
   ```

3. [ ] **Verify manifest exists and is valid**
   ```bash
   cat /Volumes/SMAOS_VAULT_B_*/VAULT_MANIFEST.json | jq .
   ```

4. [ ] **Verify workspace files present**
   ```bash
   ls -la /Volumes/SMAOS_VAULT_B_*/smaos/crates | head -20
   ```

5. [ ] **Test Shamir combine (without decrypting)**
   ```bash
   # Read shard 1, 2, and ask wife for shard 3
   # Run sss combine -k 3 and verify output is 64 hex chars
   cat /Volumes/SMAOS_VAULT_B_*/VAULT_KEY_SHARDS.txt
   ```

6. [ ] **Unmount vault**
   ```bash
   diskutil unmountDisk /dev/diskX
   ```

7. [ ] **Return Vault B to safe deposit box**
   - [ ] Box sealed and dated
   - [ ] Receipt obtained

8. [ ] **Document test results**
   - [ ] All checks passed: YES / NO
   - [ ] Any issues found: [Describe]
   - [ ] Test date: ________________

---

## Ongoing Maintenance Checklist

### Weekly (Automatic via Night Shift)
- [ ] Night Shift vault sync scheduled
  ```bash
  cd ./crates/siss-night-cycle
  ./setup_night_shift.sh --vault A --frequency nightly
  ```

- [ ] Verify Night Shift status
  ```bash
  ./scripts/status_night_shift.sh
  ```

### Monthly
- [ ] Verify all custodians still hold shards (email check-in)
  - [ ] Wife: Email sent / Confirmed receipt
  - [ ] Counsel: Email sent / Confirmed receipt
  - [ ] Foundation: N/A (until established)

- [ ] Check vault passphrase accessibility
  - [ ] 1Password login works
  - [ ] Password entry visible and correct

### Quarterly
- [ ] Mount Vault A and verify basic integrity
  ```bash
  diskutil mount /dev/diskX
  cat /Volumes/SMAOS_VAULT_A_*/VAULT_MANIFEST.json | jq .last_verified
  ```

### Annually (January)
- [ ] **Full recovery test** (see "Annual Recovery Verification" below)
- [ ] **Update custodian contact information**
  - [ ] Wife contact info current
  - [ ] Counsel contact info current
  - [ ] Update VAULT_CONTACTS.json in all vaults

- [ ] **Verify vault checksums**
  ```bash
  cd /Volumes/SMAOS_VAULT_A_*/smaos
  find . -type f -exec sha256sum {} \; | head -20
  ```

- [ ] **Rotate passphrases** (if any security concerns)
- [ ] **Test recovery with different shard combination**
  - Combine Shards: 1, 2, 4 (skip shard 3)
  - Verify output matches expected key

- [ ] **Update vault manifest** with new verification date
  ```bash
  # On mounted vault:
  cat VAULT_MANIFEST.json | jq '.verification.last_verified = "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"'
  ```

### Every 5 Years (Key Rotation)
- [ ] **Generate new master key**
  ```bash
  ./vault_init.sh A  # Reinitialize with new key
  ```

- [ ] **Generate new shards**
- [ ] **Redistribute shards to custodians**
  - [ ] New Shard 2 to personal safe
  - [ ] New Shard 3 to wife
  - [ ] New Shard 4 to counsel
  - [ ] Confirm all receipts

- [ ] **Destroy old shards** (securely shred)

---

## Annual Recovery Verification Checklist

**When:** January 1 each year  
**Time:** ~1 hour  
**Purpose:** Ensure recovery procedures still work, no data corruption

### Pre-Test
- [ ] Schedule: 2–3 hours of uninterrupted time
- [ ] Environment: Quiet, secure location
- [ ] Contact: Ensure at least one custodian available (for shard access)

### Test Steps

1. [ ] **Contact custodian for shard**
   - [ ] Send secure message: "Annual recovery test — need Shard X"
   - [ ] Await confirmation of shard availability
   - [ ] Arrange secure transmission method

2. [ ] **Gather your shards**
   - [ ] Retrieve Shard 1 or 2 from personal safe / 1Password
   - [ ] Retrieve Shard 3 from custodian (via secure channel)

3. [ ] **Retrieve vault** (Test with Vault B or C, not daily Vault A)
   ```bash
   # Retrieve Vault B from safe deposit OR
   # Contact counsel for Vault C access
   ```

4. [ ] **Mount vault**
   ```bash
   diskutil mount /dev/diskX
   ```

5. [ ] **Test Shamir combine**
   ```bash
   cat > /tmp/test_shards.txt << EOF
   [shard-1-value]
   [shard-2-value]
   [shard-3-value]
   EOF
   
   sss combine -k 3 < /tmp/test_shards.txt > /tmp/test_key.txt
   
   # Verify output is 64 hex characters
   wc -c /tmp/test_key.txt  # Should be 65 (64 chars + newline)
   ```

6. [ ] **Verify vault integrity**
   ```bash
   cat /Volumes/SMAOS_VAULT_*/*.json | jq .
   ls -la /Volumes/SMAOS_VAULT_*/smaos | head -20
   ```

7. [ ] **Verify file checksums** (spot check)
   ```bash
   cd /Volumes/SMAOS_VAULT_*/smaos
   sha256sum Cargo.toml crates/siss-graph-core/Cargo.toml crates/siss-agent-shell/Cargo.toml
   ```

8. [ ] **Securely destroy test shards**
   ```bash
   shred -u /tmp/test_shards.txt /tmp/test_key.txt
   ```

9. [ ] **Unmount vault**
   ```bash
   diskutil unmountDisk /dev/diskX
   ```

10. [ ] **Return vault to secure location**
    - [ ] Vault B: Back to safe deposit box
    - [ ] Vault C: Back to counsel escrow

11. [ ] **Document test results**
    - [ ] Date: ________________
    - [ ] Vault tested: A / B / C
    - [ ] Shards combined: 1, 2, 3 / 1, 2, 4 / [Other combination]
    - [ ] All verifications passed: YES / NO
    - [ ] Issues found: [None / Describe]
    - [ ] Action items: [None / List]

12. [ ] **Return shard to custodian**
    - [ ] Thank you email sent
    - [ ] Shard securely returned (if borrowed)

13. [ ] **Update VAULT_MANIFEST.json**
    ```bash
    # Add entry:
    "last_recovery_test": "2026-01-15",
    "recovery_test_result": "PASSED",
    "recovery_test_shards": ["1", "2", "3"]
    ```

---

## Emergency Activation Checklist

**If:** Laptop lost, stolen, or destroyed  
**Then:** Follow this procedure to recover SMAOS vision

### Immediate Actions (First Hour)

- [ ] **Locate Vault A**
  - [ ] Check home office
  - [ ] Check backup locations
  - [ ] If found, proceed to "Vault Access"

- [ ] **If Vault A Not Found, Locate Vault B**
  - [ ] Call bank managing safe deposit box
  - [ ] Request emergency access
  - [ ] Arrange retrieval ASAP (within 24 hours)
  - [ ] Proceed to "Vault Access"

- [ ] **If Vaults A & B Not Found, Activate Vault C**
  - [ ] Contact Pearl Cohen (Israeli counsel)
  - [ ] Provide emergency notification (theft / disaster)
  - [ ] Request retrieval of Vault C from escrow
  - [ ] Arrange secure delivery (may take 1–7 days)
  - [ ] Proceed to "Vault Access"

### Vault Access (Assuming Vault A Located)

- [ ] **Gather key shards**
  - [ ] Retrieve your Shard 1 (from vault) or Shard 2 (personal safe)
  - [ ] Contact wife for Shard 3
    - [ ] Phone: ________________
    - [ ] Email: ________________
  - [ ] Contact counsel for Shard 4
    - [ ] Phone: ________________
    - [ ] Email: ________________

- [ ] **Combine shards to recover master key**
  ```bash
  cat > /tmp/recovery_shards.txt << EOF
  [shard-1-value]
  [shard-3-value]
  [shard-4-value]
  EOF
  
  sss combine -k 3 < /tmp/recovery_shards.txt > /tmp/master_key.txt
  ```

- [ ] **Mount vault with master key**
  ```bash
  # macOS
  diskutil mount /dev/diskX
  
  # Linux
  sudo cryptsetup luksOpen /dev/sdX vault_decrypted
  sudo mount /dev/mapper/vault_decrypted /mnt/vault
  ```

- [ ] **Copy workspace to new computer**
  ```bash
  cp -r /Volumes/SMAOS_VAULT_A_*/smaos ~/Documents/SovereignNexus
  ```

- [ ] **Restore and verify**
  ```bash
  cd ~/Documents/SovereignNexus
  cargo build
  cargo test --all
  ```

- [ ] **Securely destroy shard data**
  ```bash
  shred -u /tmp/recovery_shards.txt /tmp/master_key.txt
  ```

- [ ] **Unmount vault**
  ```bash
  diskutil unmountDisk /dev/diskX
  ```

- [ ] **Test recovered system**
  - [ ] Git repository intact
  - [ ] All crates compile
  - [ ] Tests pass
  - [ ] Genesis keys accessible

### Post-Recovery

- [ ] **Update custodians**
  - [ ] Notify wife, counsel that recovery was successful
  - [ ] Request return of shard (if borrowed)
  - [ ] Update contact info if changed

- [ ] **Analyze what happened**
  - [ ] Determine cause of laptop loss
  - [ ] Implement preventive measures
  - [ ] Update security procedures if needed

- [ ] **Plan future vault maintenance**
  - [ ] Replace any lost vaults (if applicable)
  - [ ] Schedule rotation earlier (if shards were exposed)
  - [ ] Brief any new custodians

---

## Sign-Off Checklist

**After completing all execution and testing steps:**

- [ ] **All 3 vaults created successfully**
- [ ] **All passphrases stored in encrypted password manager**
- [ ] **All key shards distributed to custodians**
- [ ] **Initial recovery test passed**
- [ ] **Night Shift synchronization configured**
- [ ] **Annual maintenance calendar set up**

**Sign-Off:**

- [ ] **Visionary (You)**: ________________ Date: ________
- [ ] **Family Custodian**: ________________ Date: ________
- [ ] **Legal Custodian**: ________________ Date: ________

**Vision Survival Status:** ✓ ACTIVE AND DISTRIBUTED

---

## Quick Reference Commands

### Mount Vault
```bash
diskutil list external  # Find device
diskutil mount /dev/diskX
```

### Verify Vault Integrity
```bash
cat /Volumes/SMAOS_VAULT_A_*/VAULT_MANIFEST.json | jq .
ls -la /Volumes/SMAOS_VAULT_A_*/smaos/crates | wc -l
```

### Combine Shards
```bash
cat > /tmp/shards.txt << EOF
[shard-1]
[shard-2]
[shard-3]
EOF
sss combine -k 3 < /tmp/shards.txt
```

### Unmount Vault
```bash
diskutil unmountDisk /dev/diskX
```

### Show Last Sync
```bash
grep "last_sync" /Volumes/SMAOS_VAULT_A_*/VAULT_MANIFEST.json
```

---

**This checklist ensures Vision Survival Protocol is fully operational.**

**All vaults created. All shards distributed. Vision is now distributed and survivable.**

Created: May 29, 2026
