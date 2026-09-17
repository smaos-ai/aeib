# AEIB Receipt Fuzzer — Cold Outreach Playbook & Email Templates

**Standard:** DORA Art. 17(3) — Evidence Contamination & Retry Hazards  
**Primary Lead Magnet:** [https://github.com/smaos-ai/aeib-receipt-fuzzer](https://github.com/smaos-ai/aeib-receipt-fuzzer)  
**Fixed-Fee Diagnostic Offer:** €1,500 (48-hr sprint) / €2,500 (5-day audit)  
**Direct Contact:** `andrejlo123@gmail.com`

---

## ✉️ Template 1: Engineering Lead / Principal Agent Architect

**Subject:** What does your agent harness do on an HTTP 504?

```text
Hi [First Name],

Quick engineering question on your agent tool-calling pipeline:

When your agent dispatches a mutating tool call (e.g. database write, payment, or API call) and the downstream gateway responds with an HTTP 504 Gateway Timeout or a dropped TCP socket:

• Does your harness retry blindly and risk duplicate writes?
• Does it assume failure and trigger compensating rollbacks even if the transaction actually settled?
• Or does it sign an Ed25519 receipt claiming "CONFIRMED / EXECUTED" without wire evidence?

We built and open-sourced a zero-dependency wire-level fault proxy to test this exact failure mode:
👉 https://github.com/smaos-ai/aeib-receipt-fuzzer

You can run our 5-scenario CLI demo locally in 4 seconds:
  git clone https://github.com/smaos-ai/aeib-receipt-fuzzer.git
  cd aeib-receipt-fuzzer
  python3 demo_killshot.py

It injects 6 wire-level fault modes (504 timeout, TCP RST, JCS payload tampering) and evaluates whether your agent preserves uncertainty (verdict: UNKNOWN, retry_held: true) or emits Toxic Receipts.

Would you be open to running `python3 demo_killshot.py` to see if our precedence rules match how your production harnesses handle network drops?

Best regards,

Andrii Leukhin
SMAOS — Sovereign Multi-Agent Trust Infrastructure
https://github.com/smaos-ai
andrejlo123@gmail.com
```

---

## ✉️ Template 2: CISO / Head of Operational Risk (FinTech & Regulated AI)

**Subject:** AI agent evidence contamination under DORA Art. 17(3)

```text
Dear [First Name],

A critical risk emerging in enterprise autonomous AI deployments is "Evidence Contamination": when an agent SDK asserts and cryptographically signs that an action was "EXECUTED", even though the downstream system timed out.

Under DORA Art. 17(3) and the EU AI Act Art. 12, audit logs asserting state transitions that cannot be reconciled against downstream systems of record constitute compliance audit failures and operational retry hazards.

To address this, we open-sourced the AEIB Receipt Fuzzer and Toxic Receipt Detector:
👉 https://github.com/smaos-ai/aeib-receipt-fuzzer

Key capabilities:
1. Wire-Level Fault Fuzzing: Verifies fail-closed state machines under HTTP 504, connection drops, and payload collisions.
2. Property-Level Sufficiency: Enforces strict precedence:
   INVALID_INPUT → MISSING_EVIDENCE → CONFLICT → REFUSED → CONFIRMED → UNKNOWN
3. Offline Trace Scanner (diff.py): Ingests 30-day staging traces under NDA, calculates your Toxic Receipt Index (TRI %), and outputs a unified git-diff patch converting unverified claims to fail-closed UNKNOWN.

We also offer a 5-day fixed-fee Staging Forensic Audit (€2,500) for teams qualifying under discretionary procurement limits.

Would you be open to a brief technical review of the threat model and state machine specifications?

Sincerely,

Andrii Leukhin
SMAOS — Sovereign Multi-Agent Trust Infrastructure
https://github.com/smaos-ai
andrejlo123@gmail.com
```

---

## ✉️ Template 3: Node5 Meetup / Conference Direct Follow-up

**Subject:** The €1.85M → €1.90M loan edit killshot demo / slides

```text
Hi [First Name],

Great meeting you at Node5 today!

Following up on our conversation about why sandbox isolation doesn't protect against wire-level evidence contamination in autonomous agents:

Here is the open-source CLI fuzzer we ran on stage:
👉 https://github.com/smaos-ai/aeib-receipt-fuzzer

To rerun the 5 scenarios (including the €1.85M → €1.90M silent in-transit loan tampering that triggers an ex-ante HALT via JCS digest mismatch):

  git clone https://github.com/smaos-ai/aeib-receipt-fuzzer.git
  cd aeib-receipt-fuzzer
  python3 demo_killshot.py

If your team is running tool-calling agents in staging and wants to scan your JSONL logs for toxic receipts before production rollout, check out `diff.py` or let me know — happy to run a quick 48-hour diagnostic.

Cheers,

Andrii Leukhin
andrejlo123@gmail.com
https://github.com/smaos-ai
```
