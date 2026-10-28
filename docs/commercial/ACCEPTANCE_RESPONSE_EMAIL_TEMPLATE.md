# 📨 Customer-Ready Acceptance Response & Pre-Meeting Briefing Pack
## Rapid-Response Email Templates, Calendar Invite Specifications & Zero-Egress Assurance

**Dispatch Window:** Within **15 minutes** of receiving acceptance or positive interest.  
**Tone:** Concise, deeply technical, authoritative, zero enterprise friction.  
**Target Personas:** 
- **Martin Trčka** (VP Engineering / Platform Lead, Twisto / Zip Co)
- **Mirek Karpeta** (VP Engineering / Platform, Air Bank / PPF Group)
- General Banking / FinTech CISO / VP Platform

---

## 📬 1. Rapid-Response Email Templates (< 15-Minute Turnaround)

### Option A: Tailored for Martin Trčka (Twisto / Zip Co — BNPL & Payment Gateways)

**Subject:** Re: 15-min passive staging recon / Twisto BNPL payment drop drift

```text
Hi Martin,

Thanks for the quick response. Glad to hear you're open to taking a look.

We can run the 15-minute passive recon in a single 45-minute technical session. The breakdown is straightforward:
1. 00:00–05:00: Regulatory wire-fact context (DORA Art. 17 / ČNB 4-hour clock).
2. 05:00–20:00: Executing the read-only passive socket sniffer on your staging runner (or our isolated mirror).
3. 20:00–35:00: Inspecting the generated Mermaid Attack & Drift Graph to calculate your staging Overclaim Rate.
4. 35:00–45:00: Demonstrating the 5-line @proof_or_stop drop-in remedy and discussing next steps.

Two quick slots that work on our side:
• Tomorrow (Wednesday) at 14:00 CEST
• Thursday at 10:30 CEST

Let me know which window suits your calendar, or feel free to propose an alternative.

To eliminate any staging friction, I've attached our 1-page Zero-Egress Staging Brief below. The probe requires zero external pip packages, zero proxy redirection, no payload decryption, and emits 0 bytes of cloud telemetry (runs with docker run --network none).

Looking forward to catching up.

Best regards,

Andrii Leukhin
Founder & Principal Forensic Auditor
SMAOS Trust Infrastructure / SovereignNexus
Email: andrejlo123@gmail.com | Signal / Mobile: +420 [Direct Line]
Prague, Czech Republic
```

---

### Option B: Tailored for Mirek Karpeta (Air Bank / PPF Group — Tier-1 Digital Banking)

**Subject:** Re: 15-minute read-only staging audit / Air Bank agent wire-fact verification

```text
Hi Mirek,

Appreciate the swift follow-up. 

We would be glad to walk through the 15-minute passive staging recon with you and your platform security team. 

Our session is strictly engineered for 45 minutes:
1. Stage 1 (5 mins): ČNB / DORA Art. 17 supervisory inspection criteria on unanchored agent writes.
2. Stage 2 (15 mins): Live execution of our passive eBPF/socket probe (zero installation, zero cloud egress).
3. Stage 3 (15 mins): Revealing the real-time Mermaid Drift Graph & quantitative Overclaim Rate on staging loan/disbursement traces.
4. Stage 4 (10 mins): Reviewing the drop-in 5-line remedy (@proof_or_stop + smaos-mcp) and the €1,500 diagnostic SOW.

Would either of these times suit you and your team?
• Thursday at 11:00 CEST
• Friday at 14:00 CEST

Below you will find our Zero-Egress Staging Assurance Brief. The probe executes completely offline with zero binary dependencies, ensuring zero impact on your staging environments and zero exposure of bank telemetry.

Looking forward to our session.

Warm regards,

Andrii Leukhin
Founder & Principal Forensic Auditor
SMAOS Trust Infrastructure / SovereignNexus
Email: andrejlo123@gmail.com | Signal / Mobile: +420 [Direct Line]
Prague, Czech Republic
```

---

### Option C: Universal Tier-1 Enterprise Banking / FinTech Template

**Subject:** Re: 15-min passive staging recon / Agent wire-fact overclaim audit

```text
Hi [First Name],

Great to connect. 

We can run the 15-minute passive recon within a focused 45-minute live screen share. During this session, we will:
1. Passively inspect staging agent socket traffic (read-only, zero binary install, 0 bytes cloud egress).
2. Generate your live Mermaid Attack & Drift Graph to calculate your Wire-Fact Overclaim Rate under network drop conditions.
3. Demonstrate how a 5-line drop-in decorator (@proof_or_stop) halts duplicate mutations and provides full DORA Article 17 safe harbor compliance.

Would either of the following slots work for a Google Meet / Teams session?
• [Slot 1: Date + Time CEST]
• [Slot 2: Date + Time CEST]

If your security architects need to review our execution parameters beforehand, please review our Zero-Egress Staging Host Brief outlined below.

Best regards,

Andrii Leukhin
Founder & Principal Forensic Auditor
SMAOS Trust Infrastructure / SovereignNexus
Email: andrejlo123@gmail.com
```

---

## 📅 2. Calendar Invite Specification

When the lead confirms a time slot, immediately dispatch a calendar invite with the following parameters:

- **Meeting Title:** `SMAOS x [Client Entity]: 15-Min Staging Passive Recon & DORA Wire-Fact Audit`
- **Duration:** 45 Minutes
- **Video Link:** Google Meet / Microsoft Teams / Zoom (Client Preference)
- **Invitees:** `[Lead Email]`, `andrejlo123@gmail.com`
- **Description:**

```text
Session Agenda:
• 00:00–05:00: DORA Article 17 & ČNB Supervisory Context (The 4-hour incident clock).
• 05:00–20:00: Live 15-Minute Passive Recon Execution (eBPF socket sniffer on staging runner).
• 20:00–30:00: Forensic Analysis: Mermaid Attack & Drift Graph & Overclaim Rate Scorecard.
• 30:00–40:00: Drop-In Technical Remedy (@proof_or_stop & smaos-mcp gateway).
• 40:00–45:00: Next Steps: Review of the €1,500 5-Day Staging Forensic Diagnostic SOW.

Technical Prerequisites:
• Pure Python 3.10+ standard library (zero pip packages).
• Strictly air-gapped / local execution (docker run --network none or offline host).
• Zero TLS certificate injection, zero payload alteration, zero data retention.

Presenter:
Andrii Leukhin (Founder & Principal Forensic Auditor, SMAOS Trust Infrastructure)
Direct: andrejlo123@gmail.com
```

---

## 🔒 3. Pre-Meeting Zero-Egress Staging Assurance Brief

*(Include this section in the email body or as an attached PDF for the client's Infrastructure and Security Architecture teams.)*

### Executive Overview & Invariant Guarantees
The SMAOS Passive Recon Probe (`smaos-probe`) is designed to meet the strictest financial infrastructure security guidelines (ČNB Decree No. 367/2022 Coll., BaFin MaRisk/BAIT, DORA Article 17/28):

1. **Zero External Network Egress (Air-Gap Invariant):**
   - The probe makes **0 outbound network connections**.
   - Verified via: `docker run --network none` or local host verification:
     ```bash
     tcpdump -i any not host 127.0.0.1 -c 1
     # Result: 0 packets captured
     ```
2. **Zero Dependency Footprint:**
   - Pure Python standard library (`sys`, `os`, `socket`, `time`, `json`, `subprocess`).
   - No external pip packages, no C-extensions, no third-party package repository downloads (`npm`, `pip`, `cargo`).
3. **Strictly Non-Invasive / Read-Only:**
   - **No packet injection:** The probe passively reads existing OS socket states (`/proc/net/tcp` or `ss -tina`).
   - **No TLS MITM / Decryption:** The probe does NOT require root CA certificates or payload inspection. It correlates TCP handshake/RST state transitions and HTTP status codes against database commit timestamps.
   - **Zero Schema or Code Modification:** Does not alter existing databases, tables, or application files.
4. **Data Privacy & Ephemeral Retention:**
   - Zero customer PII or transaction secrets are ingested or stored.
   - All diagnostic reports and Mermaid drift graphs are output locally to the client's staging host directory.

### Host Machine Requirements
- **OS:** Linux (Ubuntu 20.04+, RHEL 8+, Debian 11+), macOS (Darwin 20+), or Docker runtime.
- **Runtimes Supported:** Python 3.10+, Node.js 18+, or compiled binaries (Go/Rust).
- **Permissions:** Standard non-privileged user (Root is NOT required; optional for eBPF kernel socket tracing).
- **Execution Script:**
  ```bash
  # Standalone 180-line audit script (human-readable, open for inspection):
  python3 smaos-probe/src/probe.py --duration 15 --mermaid drift_graph.mmd -o audit_report.json
  ```

---

## ⚡ 4. Internal FDE Escalation Protocol

If the target's security architect responds requesting deeper compliance verification:
1. Send `docs/sovereign/EUROPEAN_SOVEREIGNTY_BRIEF.md` (GDPR Chapter V & DORA Article 28 cross-border transfer analysis).
2. Provide pre-computed SHA-256 checksums of `smaos-probe/src/probe.py`:
   ```bash
   shasum -a 256 smaos-probe/src/probe.py
   ```
3. Offer an alternative: Run the walkthrough on a sanitized, pre-loaded SMAOS staging mirror that exactly mirrors Twisto or Air Bank microservice topology if internal staging approvals take more than 24 hours.
