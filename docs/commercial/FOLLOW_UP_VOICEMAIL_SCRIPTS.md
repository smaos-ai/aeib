# 🎙️ 24-Hour Follow-Up Phone & LinkedIn Voicemail Scripts
## High-Impact, Zero-Sales-Breath Touchpoints for Prague FinTech & Banking Executives

**Target Timing:** Dispatched **24 hours** after initial email or LinkedIn message dispatch.  
**Delivery Persona:** Forward Deployed Engineer / Principal Forensic Auditor (Andrii Leukhin).  
**Tone & Cadence:** Low vocal cadence, peer-to-peer technical peer, zero sales breath, focused strictly on wire reality and regulatory compliance.

---

## 📞 Script 1: Angle A Follow-Up (Shadow MCP & Tool Drift)
**Primary Target:** **Martin Trčka** (VP Engineering / Platform Lead, Twisto / Zip Co) or Enterprise CISOs & Heads of AppSec.

### Phone Call / Voicemail (45–60 Seconds)
> *"Hi Martin, Andrii here from SMAOS Trust Infrastructure in Prague.*  
> 
> *I sent you a brief note yesterday regarding MCP tool execution security in your staging payment workflows.*  
> 
> *The reason I'm following up directly: With over 30 CVEs hitting MCP infrastructure this year and 91% of servers relying on static API keys, the primary risk we're seeing across European fintechs isn't prompt injection—it's **silent tool drift** and false confirmations when downstream checkout webhooks experience an HTTP 504 timeout.*  
> 
> *We have an air-gapped, 180-line Python probe that runs locally with `--network none`. In 15 minutes, it maps your active agent processes and proves whether any of your workers are quietly asserting successful state writes after dropped connections.*  
> 
> *No software installation, no vendor onboarding, zero cloud telemetry. If you're open to a 10-minute terminal screen share this Thursday or Friday, let me know. My direct line is +420 [Number], or just reply to yesterday's email. Have a great day."*

### LinkedIn Voice Note Alternative (30 Seconds)
> *"Hi Martin, quick follow-up to my note yesterday on LinkedIn regarding MCP tool drift at Twisto.*  
> *Most teams assume their agent harnesses handle gateway drops safely, but under transport contention, standard SDKs frequently mask 504 drops as completed transactions.*  
> *I’d love to show you a 10-minute live screen share of our air-gapped probe catching this drift in real time. Let me know if Thursday afternoon works for a quick look."*

---

## 📞 Script 2: Angle B Follow-Up (Machine Micropayments & Stripe 402 Anomaly)
**Primary Target:** **Mirek Karpeta** (VP Engineering / Platform, Air Bank / PPF Group) or FinTech CTOs & VP Infrastructure.

### Phone Call / Voicemail (45–60 Seconds)
> *"Hi Mirek, Andrii Leukhin calling from SMAOS in Prague.*  
> 
> *Following up on my note from yesterday regarding agentic settlement and the **Stripe 402 upstream_timeout anomaly**.*  
> 
> *As retail banks and fintechs begin testing autonomous settlement rails and machine payments, we've identified a dangerous blind spot: when an upstream gateway returns `402 upstream_timeout`, naive agent retry logic misreads the status code as an unpaid invoice, re-signs the transaction, and triggers duplicate disbursements on severed wires.*  
> 
> *Under ČNB DORA Article 17, failing to detect and halt unanchored state mutations within 4 hours is classified as an unnotified major ICT incident.*  
> 
> *We built an out-of-band wire invariant engine that forces dropped payment wires into an immutable `UNKNOWN` state, halting treasury drainage before database commit.*  
> 
> *I'd like to show you a 15-minute terminal simulation of this failure mode running in an air-gapped container. Would Thursday at 11:00 CEST or Friday afternoon suit you? You can reach me back at +420 [Number] or on email. Thanks Mirek."*

### LinkedIn Voice Note Alternative (30 Seconds)
> *"Hi Mirek, Andrii here following up on my email regarding agentic wire drops at Air Bank.*  
> *When upstream payment gateways encounter timeouts, agent retry loops often trigger duplicate ledger writes that breach DORA Article 17.*  
> *We can run a 15-minute passive recon on your staging runner to verify whether your settlement microservices have any unanchored confirmations. Let me know if you're open to a quick 10-minute terminal demo this week."*

---

## 📞 Script 3: Angle C Follow-Up (Regulatory Safe Harbor & DORA Article 17)
**Primary Target:** Chief Risk Officers (CRO), Heads of Regulatory Compliance, or Lead Security Architects.

### Phone Call / Voicemail (45–60 Seconds)
> *"Hello [Name], Andrii Leukhin calling from SovereignNexus.*  
> 
> *I sent you our DORA Article 17 Forensic Brief yesterday regarding autonomous agent auditability.*  
> 
> *With ČNB and EBA supervisory inspections shifting in 2026 from guidance to active register cross-checks, standard JSON schema validation is no longer sufficient. If an agent SDK logs 'CONFIRMED' on a transaction where the physical wire dropped, that constitutes an unnotified major incident under Article 17.*  
> 
> *We provide a fixed-scope, 5-day offline staging diagnostic for €1,500 that audits 250 historical traces, pre-populates your `RT.01.03` xBRL-CSV Register, and delivers an executive dossier for your Board Risk Committee.*  
> 
> *I'd welcome 10 minutes on a screen share to demonstrate our offline WASM verifier. Please check your inbox for my email with `dora-evidence-pack.zip`, or call me directly at +420 [Number]. Thank you."*

---

## ⚡ Live Pickup Protocol (When the Executive Answers)

If the prospect answers the phone live, follow the **3-Question Alignment**:

1. **Permission / Hook:**  
   *"Martin / Mirek, did I catch you in the middle of a release, or do you have 90 seconds?"*
2. **The Forensic Pivot:**  
   *"When your staging workers hit an upstream 504 gateway timeout or TCP drop, does your observability stack verify that the wire actually completed, or does it trust the SDK's internal catch-block?"*
3. **The Low-Friction Offer:**  
   *"We don't ask you to install any software. I can share my terminal for 10 minutes and show you the exact Mermaid drift graph our probe generates on an air-gapped runner. Would tomorrow at 14:00 CEST work for a quick look?"*
