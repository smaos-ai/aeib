#!/usr/bin/env python3
"""
sync_outreach_tracker.py — Enterprise CISO Outreach CRM Synchronizer
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Generates and updates:
  - scratch/ciso_outreach_tracker.csv
  - scratch/ciso_outreach_tracker.xlsx
  - Brain artifacts copies for Studio panel download

Features:
  - Wave 1 Tier-1 Prague Fintech targets (Dispatched 2026-09-22):
      • Michal Černý (Twisto)
      • Jan Gargulák (Dateio)
      • Tomas Widlak (Lemonero)
      • Otakar Zich (Roger / Investown)
      • Martin Trčka (Resistant AI)
  - Waves 2 & 3 Enterprise Bank and Cross-Border architectures.

Zero external dependencies (pure Python standard library).
"""

import csv
import os
import shutil
import zipfile

BRAIN_DIR = "/Users/andriileukhin/.gemini/antigravity/brain/5d79cd4e-030d-4b16-91b2-f9330b16dfda"
SCRATCH_DIR = "/Users/andriileukhin/Documents/SovereignNexus/scratch"

TARGETS = [
    {
        "Target_ID": "REV-01",
        "Target_Name": "Michal Černý",
        "Role": "CTO",
        "Organization": "Twisto (Zip Co)",
        "Email": "michal.cerny@twisto.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "FinTech / BNPL Payments",
        "Outreach_Channel": "Email & LinkedIn",
        "Connection_Note_Sent_At": "2026-09-22 12:45 CEST",
        "Briefing_Attached": "YES",
        "Status": "DISPATCHED_WAVE_1",
        "Next_Followup_Date": "2026-09-25",
        "Assigned_Angle": "Angle B (Machine Pay x402 / Ledger Timeouts)",
        "Angle_Hook": (
            "BNPL mutating ledger timeouts & double-allocation risk under 504"
            " drops."
        ),
        "Notes": (
            "Wave 1 Tier-1 Fintech. Sent technical diagnostic pitch with"
            " staging test invite."
        ),
    },
    {
        "Target_ID": "REV-02",
        "Target_Name": "Jan Gargulák",
        "Role": "CTO",
        "Organization": "Dateio",
        "Email": "jan.gargulak@dateio.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "Card-Linked Offers & Banking APIs",
        "Outreach_Channel": "Email & LinkedIn",
        "Connection_Note_Sent_At": "2026-09-22 12:45 CEST",
        "Briefing_Attached": "YES",
        "Status": "DISPATCHED_WAVE_1",
        "Next_Followup_Date": "2026-09-25",
        "Assigned_Angle": "Angle A (Shadow MCP / Tool Drift)",
        "Angle_Hook": "Merchant API sync, MCP tool drift & silent 504 drops.",
        "Notes": (
            "Wave 1 Tier-1 Fintech. Sent technical diagnostic pitch with"
            " staging test invite."
        ),
    },
    {
        "Target_ID": "REV-03",
        "Target_Name": "Tomas Widlak",
        "Role": "Head of Engineering",
        "Organization": "Lemonero",
        "Email": "tomas.widlak@lemonero.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "E-Commerce Revenue Financing & Embedded Lending",
        "Outreach_Channel": "Email & LinkedIn",
        "Connection_Note_Sent_At": "2026-09-22 12:45 CEST",
        "Briefing_Attached": "YES",
        "Status": "DISPATCHED_WAVE_1",
        "Next_Followup_Date": "2026-09-25",
        "Assigned_Angle": "Angle B (Stripe 402 / Gateway Drops)",
        "Angle_Hook": (
            "E-commerce payment gateway drops & Stripe 402 timeouts."
        ),
        "Notes": (
            "Wave 1 Tier-1 Fintech. Sent technical diagnostic pitch with"
            " staging test invite."
        ),
    },
    {
        "Target_ID": "REV-04",
        "Target_Name": "Otakar Zich",
        "Role": "CTO",
        "Organization": "Roger / Investown",
        "Email": "otakar.zich@roger.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "Invoice Factoring & PropTech Financing",
        "Outreach_Channel": "Email & LinkedIn",
        "Connection_Note_Sent_At": "2026-09-22 12:45 CEST",
        "Briefing_Attached": "YES",
        "Status": "DISPATCHED_WAVE_1",
        "Next_Followup_Date": "2026-09-25",
        "Assigned_Angle": "Angle C (Regulatory DORA Art. 17)",
        "Angle_Hook": (
            "Invoice factoring settlement verification & DORA Art. 17 major"
            " incident classification."
        ),
        "Notes": (
            "Wave 1 Tier-1 Fintech. Sent technical diagnostic pitch with"
            " staging test invite."
        ),
    },
    {
        "Target_ID": "REV-05",
        "Target_Name": "Martin Trčka",
        "Role": "VP of Engineering",
        "Organization": "Resistant AI",
        "Email": "martin.trcka@resistant.ai",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "Adversarial AI Security & Fraud Prevention",
        "Outreach_Channel": "Email & LinkedIn",
        "Connection_Note_Sent_At": "2026-09-22 12:45 CEST",
        "Briefing_Attached": "YES",
        "Status": "DISPATCHED_WAVE_1",
        "Next_Followup_Date": "2026-09-25",
        "Assigned_Angle": "Angle A (Adversarial Wire Fuzzing / OWASP MCP03)",
        "Angle_Hook": (
            "Adversarial wire fuzzing & Agentic OWASP MCP03 rug pulls."
        ),
        "Notes": (
            "Wave 1 Tier-1 Fintech. Sent technical diagnostic pitch with"
            " staging test invite."
        ),
    },
    {
        "Target_ID": "REV-11",
        "Target_Name": "Dr. Florian Becker",
        "Role": "Chief Information Security Officer",
        "Organization": "Erste Group Bank AG",
        "Email": "florian.becker@erstegroup.com",
        "Jurisdiction": "Vienna (AT)",
        "Segment": "Tier-1 Regional Group Parent",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_2",
        "Next_Followup_Date": "2026-09-26",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": "Centralizing CEE agent evidence under DORA Article 28(3).",
        "Notes": "CEE group-wide agent governance standard.",
    },
    {
        "Target_ID": "REV-12",
        "Target_Name": "Stefan Steiner",
        "Role": "Lead Payments & Settlement Architect",
        "Organization": "Raiffeisen Bank International",
        "Email": "stefan.steiner@rbinternational.com",
        "Jurisdiction": "Vienna (AT)",
        "Segment": "Tier-1 International Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_2",
        "Next_Followup_Date": "2026-09-26",
        "Assigned_Angle": "Angle B (Machine Pay x402)",
        "Angle_Hook": (
            "x402 wire settlement invariant halting duplicate clearing payouts"
            " on severed wires."
        ),
        "Notes": "Core settlement API timeouts and saga rollback guarantees.",
    },
    {
        "Target_ID": "REV-13",
        "Target_Name": "Markus Weber",
        "Role": "Head of Operational Risk & ICT Security",
        "Organization": "HypoVereinsbank (UniCredit Germany)",
        "Email": "markus.weber@unicredit.de",
        "Jurisdiction": "Munich (DE)",
        "Segment": "Tier-1 Commercial Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_2",
        "Next_Followup_Date": "2026-09-26",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": (
            "BaFin-ready air-gapped audit evidence with zero cloud egress."
        ),
        "Notes": "BaFin BAIT / DORA pre-production safe harbor.",
    },
    {
        "Target_ID": "REV-14",
        "Target_Name": "Dr. Christian Meyer",
        "Role": "CISO Corporate Bank",
        "Organization": "Deutsche Bank AG",
        "Email": "christian.meyer@db.com",
        "Jurisdiction": "Frankfurt (DE)",
        "Segment": "Tier-1 Global Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_2",
        "Next_Followup_Date": "2026-09-26",
        "Assigned_Angle": "Angle A (Shadow MCP)",
        "Angle_Hook": (
            "Global enterprise MCP swarm schema pinning & credential"
            " scrubbing."
        ),
        "Notes": (
            "Global enterprise scale MCP swarms. Elena Bianchi €50k loan case"
            " study."
        ),
    },
    {
        "Target_ID": "REV-15",
        "Target_Name": "Beat Zimmermann",
        "Role": "Head of Core Banking Systems",
        "Organization": "UBS Wealth Management",
        "Email": "beat.zimmermann@ubs.com",
        "Jurisdiction": "Zurich (CH)",
        "Segment": "Global Wealth Management",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_2",
        "Next_Followup_Date": "2026-09-26",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": (
            "Swiss sovereign data protection (zero US CLOUD Act exposure)."
        ),
        "Notes": (
            "FINMA Circular 2023/1 alignment and sovereign air-gapped"
            " execution."
        ),
    },
    {
        "Target_ID": "REV-21",
        "Target_Name": "Mirek Karpeta",
        "Role": "VP Engineering / Platform",
        "Organization": "Air Bank (PPF Group)",
        "Email": "mirek.karpeta@airbank.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "Tier-1 Digital Retail Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_3",
        "Next_Followup_Date": "2026-09-27",
        "Assigned_Angle": "Angle B (Machine Pay x402)",
        "Angle_Hook": (
            "Stripe 402 upstream_timeout trap & consumer loan disbursement"
            " double-pay prevention."
        ),
        "Notes": (
            "15-min read-only staging audit with eBPF probe showing silent 504"
            " reverse-proxy drops."
        ),
    },
    {
        "Target_ID": "REV-22",
        "Target_Name": "Daniel Čermák",
        "Role": "Head of Operational Risk & Architecture",
        "Organization": "UniCredit Bank Slovakia",
        "Email": "daniel.cermak@unicreditgroup.sk",
        "Jurisdiction": "Bratislava (SK)",
        "Segment": "Tier-1 Cross-Border Commercial",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_3",
        "Next_Followup_Date": "2026-09-27",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": (
            "NBS / ECB cross-border compliance alignment & xBRL-CSV export."
        ),
        "Notes": "NBS / ECB cross-border compliance alignment.",
    },
    {
        "Target_ID": "REV-23",
        "Target_Name": "Martin Brachtl",
        "Role": "Head of Digital Architecture & APIs",
        "Organization": "Česká spořitelna (Erste Group)",
        "Email": "martin.brachtl@csas.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "Tier-1 Retail Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_3",
        "Next_Followup_Date": "2026-09-27",
        "Assigned_Angle": "Angle A (Shadow MCP)",
        "Angle_Hook": (
            "API gateway retry storms & MCP tool expansion containment."
        ),
        "Notes": "API gateway retry storms and downstream circuit breaking.",
    },
    {
        "Target_ID": "REV-24",
        "Target_Name": "Jan Široký",
        "Role": "Chief Technology Officer",
        "Organization": "Mews Systems",
        "Email": "jan.siroky@mews.com",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "Global Hospitality FinTech / Unicorn",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_3",
        "Next_Followup_Date": "2026-09-27",
        "Assigned_Angle": "Angle B (Machine Pay x402)",
        "Angle_Hook": (
            "x402 merchant micropayment routing & stablecoin double-spend"
            " prevention."
        ),
        "Notes": "Merchant payment routing & merchant settlement timeouts.",
    },
    {
        "Target_ID": "REV-25",
        "Target_Name": "Petr Kopecký",
        "Role": "Head of Security & IT Risk",
        "Organization": "MONETA Money Bank",
        "Email": "petr.kopecky@moneta.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "Tier-1 Czech Retail & SME Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_3",
        "Next_Followup_Date": "2026-09-27",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": "ČNB compliance inspection on AI decision automation.",
        "Notes": "ČNB compliance inspection on AI decision automation.",
    },
    {
        "Target_ID": "REV-26",
        "Target_Name": "Lukáš Kovárník",
        "Role": "VP Infrastructure & Core",
        "Organization": "Rohlik Group",
        "Email": "lukas.kovarnik@rohlik.cz",
        "Jurisdiction": "Prague (CZ)",
        "Segment": "European E-Commerce & FinTech Scale-Up",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_4",
        "Next_Followup_Date": "2026-09-28",
        "Assigned_Angle": "Angle B (Machine Pay x402)",
        "Angle_Hook": (
            "Treasury automation, multi-country vendor disbursement loops."
        ),
        "Notes": "Treasury automation, multi-country vendor disbursement loops.",
    },
    {
        "Target_ID": "REV-27",
        "Target_Name": "Thomas Schaufler",
        "Role": "Head of Retail & Digital Products",
        "Organization": "Commerzbank AG",
        "Email": "thomas.schaufler@commerzbank.com",
        "Jurisdiction": "Frankfurt (DE)",
        "Segment": "Tier-1 German Commercial Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_4",
        "Next_Followup_Date": "2026-09-28",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": "BaFin BAIT supervisory letters & agent trace auditability.",
        "Notes": "BaFin BAIT supervisory letters & agent trace auditability.",
    },
    {
        "Target_ID": "REV-28",
        "Target_Name": "Alexander Graf",
        "Role": "Chief Information Officer",
        "Organization": "Erste Digital",
        "Email": "alexander.graf@erstedigital.com",
        "Jurisdiction": "Vienna (AT)",
        "Segment": "Banking Technology Group Hub",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_4",
        "Next_Followup_Date": "2026-09-28",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": "Centralizing CEE IT infrastructure audit trails.",
        "Notes": "Centralizing CEE IT infrastructure audit trails.",
    },
    {
        "Target_ID": "REV-29",
        "Target_Name": "Sophie Delorme",
        "Role": "Head of ICT Risk & Supervisory Governance",
        "Organization": "BNP Paribas Fortis",
        "Email": "sophie.delorme@bnpparibasfortis.com",
        "Jurisdiction": "Brussels (BE)",
        "Segment": "Tier-1 Pan-European Bank",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_4",
        "Next_Followup_Date": "2026-09-28",
        "Assigned_Angle": "Angle C (Regulatory DORA)",
        "Angle_Hook": "NBB / EBA cross-border supervisory reporting.",
        "Notes": "NBB / EBA cross-border supervisory reporting.",
    },
    {
        "Target_ID": "REV-30",
        "Target_Name": "Marco Benetti",
        "Role": "Chief Security Architect",
        "Organization": "Intesa Sanpaolo",
        "Email": "marco.benetti@intesasanpaolo.com",
        "Jurisdiction": "Milan (IT)",
        "Segment": "Tier-1 Italian Banking Group",
        "Outreach_Channel": "LinkedIn",
        "Connection_Note_Sent_At": "",
        "Briefing_Attached": "YES",
        "Status": "QUEUED_BATCH_4",
        "Next_Followup_Date": "2026-09-28",
        "Assigned_Angle": "Angle A (Shadow MCP)",
        "Angle_Hook": (
            "Banca d'Italia DORA alignment & core banking AI verification."
        ),
        "Notes": "Banca d'Italia DORA alignment & core banking AI verification.",
    },
]

FIELDNAMES = [
    "Target_ID",
    "Target_Name",
    "Role",
    "Organization",
    "Email",
    "Jurisdiction",
    "Segment",
    "Outreach_Channel",
    "Connection_Note_Sent_At",
    "Briefing_Attached",
    "Status",
    "Next_Followup_Date",
    "Assigned_Angle",
    "Angle_Hook",
    "Notes",
]


def export_csv(filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for t in TARGETS:
            writer.writerow(t)


def export_xlsx(csv_path: str, xlsx_path: str):
    os.makedirs(os.path.dirname(xlsx_path), exist_ok=True)
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    sheet_data = []
    for r_idx, row in enumerate(reader, 1):
        cols = []
        for c_idx, val in enumerate(row, 1):
            col_letter = (
                chr(64 + c_idx) if c_idx <= 26 else "A" + chr(64 + c_idx - 26)
            )
            escaped = (
                val.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            cols.append(
                f'<c r="{col_letter}{r_idx}"'
                f' t="inlineStr"><is><t>{escaped}</t></is></c>'
            )
        sheet_data.append(f'<row r="{r_idx}">{" ".join(cols)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet'
        ' xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(sheet_data) + "</sheetData></worksheet>"
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types'
        ' xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels"'
        ' ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships'
        ' xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    wb = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook'
        ' xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="CISO_Outreach_Pipeline" sheetId="1"'
        ' r:id="rId1"/></sheets>'
        "</workbook>"
    )

    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships'
        ' xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
        ' Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    with zipfile.ZipFile(xlsx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", wb)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def main():
    scratch_csv = os.path.join(SCRATCH_DIR, "ciso_outreach_tracker.csv")
    scratch_xlsx = os.path.join(SCRATCH_DIR, "ciso_outreach_tracker.xlsx")
    brain_csv = os.path.join(BRAIN_DIR, "ciso_outreach_tracker.csv")
    brain_xlsx = os.path.join(BRAIN_DIR, "ciso_outreach_tracker.xlsx")

    export_csv(scratch_csv)
    export_xlsx(scratch_csv, scratch_xlsx)

    shutil.copyfile(scratch_csv, brain_csv)
    shutil.copyfile(scratch_xlsx, brain_xlsx)

    print(f"✅ Outreach tracker updated with {len(TARGETS)} enterprise targets.")
    print(f"   CSV : {scratch_csv}")
    print(f"   XLSX: {scratch_xlsx}")
    print(f"   Synced to Brain Studio Panel: {brain_xlsx}")


if __name__ == "__main__":
    main()
