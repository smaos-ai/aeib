# GPG Encryption & Transmission Protocol (Personal Mode)

**Status:** Ready to execute  
**Timeline:** 30 minutes to complete encryption

---

## Step 1: Create Transmission Package (Local)

```bash
cd ~/.smaos/patent/
cat AXIOM_PROVISIONAL_CLAIMS_FINAL.md COUNSEL_COVER_LETTER.md > AXIOM_FILING_PACKAGE.txt
```

## Step 2: Encrypt with GPG (AES-256 Symmetric)

```bash
gpg --cipher-algo AES256 --symmetric AXIOM_FILING_PACKAGE.txt
# Output: AXIOM_FILING_PACKAGE.txt.gpg
# GPG will prompt for passphrase (use strong passphrase, 32+ chars)
```

**Store passphrase securely:**
- Write passphrase on paper (air-gapped, not digital)
- Transmit via Signal (separate channel, not email)
- Message format: "AXIOM filing passphrase: [32-char passphrase]"

## Step 3: Verify Encrypted Package

```bash
gpg --list-only AXIOM_FILING_PACKAGE.txt.gpg
# Confirms encryption is valid
```

## Step 4: Transmission to Zysman Law

**Option A: Email (encrypted attachment)**
```
To: [counsel_email@zysman.law]
Subject: AXIOM Provisional Filing Package (Encrypted GPG)
Body: 
"Pearl,
Attached: AXIOM_FILING_PACKAGE.txt.gpg
Passphrase: [sent via Signal, separately]
Ready for immediate electronic filing.
Andrej"
```

**Option B: Sneakernet (USB + face-to-face in Israel)**
- Copy AXIOM_FILING_PACKAGE.txt.gpg to USB drive
- Transport to Israel (June 3–5)
- Deliver in person to Pearl Cohen
- Transmit passphrase via Signal during meeting

**RECOMMENDED: Option A (email) if counsel can receive GPG files; Option B (Sneakernet) if maximum security required**

## Step 5: Logging Filing Intent to EXEC_LOG.json

```bash
# After transmission confirmation:
echo '{
  "event": "patent_filing_intent_locked",
  "timestamp": "2026-05-31T23:30:00Z",
  "packages": [
    "AXIOM_PROVISIONAL_CLAIMS_FINAL.md",
    "COUNSEL_COVER_LETTER.md"
  ],
  "filing_strategy": "Offensive Mode (electronic submission before Israel trip)",
  "transmitted_to": "Zysman Law",
  "priority_date_target": "2026-06-02T23:59:00Z",
  "merkle_proof": "[SHA256 hash of encrypted package]"
}' >> ~/.smaos/EXEC_LOG.json
```

---

## Critical Success Factors

1. ✅ **Claims locked** (RCE + Capsule + IVB, ψ-operator removed, prior art defense solid)
2. ⏳ **Encryption ready** (GPG AES-256, passphrase to be transmitted via Signal)
3. ⏳ **Counsel contact confirmed** (Pearl Cohen email or meeting confirmation)
4. ⏳ **Electronic filing pathway confirmed** (USPTO/ILPO direct submission vs. counsel filing service)

---

## Timeline to June 2 EOD

- **Now (23:00 UTC, May 31):** Execute GPG encryption (30 min)
- **23:30 UTC, May 31:** Transmit encrypted package to counsel (email or Sneakernet prep)
- **00:00–12:00 UTC, June 1:** Counsel review + filing confirmation
- **12:00–23:59 UTC, June 1–2:** Electronic submission to USPTO/ILPO
- **23:59 UTC, June 2:** Priority date locked ✅

---

**NEXT ACTION:** Execute GPG encryption when counsel email confirmed.
