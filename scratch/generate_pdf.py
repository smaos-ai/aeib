#!/usr/bin/env python3
"""
generate_pdf.py — Generates toxic-receipt-executive-briefing.pdf
High-contrast executive layout with crimson alert callout, dark slate section headers,
empirical KPI telemetry matrix, and commercial CTA for CISO/Risk Committees.
"""

import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and render total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header (page 2)
        if self._pageNumber > 1:
            self.drawString(54, 748, "SOVEREIGN MULTI-AGENT OS (SMAOS) • CISO EXECUTIVE BRIEFING")
            self.drawRightString(612 - 54, 748, "RESTRICTED / RISK COMMITTEE EYES ONLY")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 740, 612 - 54, 740)

        # Footer (all pages)
        self.setFont("Helvetica", 6.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(54, 34, "Legal Status: 5-Day Diagnostic is an independent research activity. A formal Czech s.r.o. will be established prior to commercial deployment. No warranties provided.")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 34, page_str)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 46, 612 - 54, 46)
        
        self.restoreState()


def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom palette
    c_primary = colors.HexColor("#0F172A")    # Dark slate
    c_secondary = colors.HexColor("#1E293B")  # Medium slate
    c_crimson = colors.HexColor("#991B1B")    # Crimson dark
    c_crimson_bg = colors.HexColor("#FEF2F2") # Rose 50
    c_crimson_border = colors.HexColor("#DC2626") # Crimson bright
    c_cyan = colors.HexColor("#0284C7")       # Cyan 600
    c_text = colors.HexColor("#0F172A")
    c_muted = colors.HexColor("#475569")
    c_cta_bg = colors.HexColor("#F8FAFC")
    c_cta_border = colors.HexColor("#2563EB")

    # Typography styles
    styles.add(ParagraphStyle(
        "DocSuperHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=c_cyan,
        textTransform="uppercase",
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=c_primary,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=c_muted,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        "AlertTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13.5,
        textColor=c_crimson,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "AlertBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#7F1D1D"),
    ))
    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=c_text,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "TableHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=c_primary,
    ))
    styles.add(ParagraphStyle(
        "TableCellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_muted,
    ))
    styles.add(ParagraphStyle(
        "CtaTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "CtaBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
    ))

    story = []

    # =========================================================================
    # PAGE 1: Core Framing, Crimson Alert & Empirical KPI Matrix
    # =========================================================================
    story.append(Paragraph("Sovereign Multi-Agent OS • Enterprise Risk Architecture", styles["DocSuperHeader"]))
    story.append(Paragraph("The Toxic Receipt Crisis in Enterprise Autonomous AI", styles["DocTitle"]))
    story.append(Paragraph("Why Model-Level Alignment Fails Against Transport Faults & How Out-of-Band Wire Verification Enforces Deterministic Truth", styles["DocSubtitle"]))

    # ── Crimson Alert Callout ───────────────────────────────────────────
    alert_content = [
        [
            Paragraph("🚨 CRITICAL VULNERABILITY ALERT: THE TOXIC RECEIPT PROBLEM", styles["AlertTitle"])
        ],
        [
            Paragraph(
                "When multi-tool autonomous agents (MCP swarms, banking assistants) execute downstream APIs, "
                "transient transport drops (<b>HTTP 504 Gateway Timeouts, socket resets</b>) cause models to "
                "assume successful settlement based on internal conversational context rather than physical wire facts. "
                "The agent asserts <b>CONFIRMED</b> despite zero physical execution, generating <b>Toxic Receipts</b> that "
                "trigger un-reconciled ledger drift, duplicate disbursements, and immediate regulatory violation under "
                "<b>EU DORA Article 17(3)</b> and <b>EU AI Act Article 14</b>.",
                styles["AlertBody"]
            )
        ]
    ]
    alert_table = Table(alert_content, colWidths=[504])
    alert_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_crimson_bg),
        ("BOX", (0, 0), (-1, -1), 1.5, c_crimson_border),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
    ]))
    story.append(alert_table)
    story.append(Spacer(1, 10))

    # ── Section 1: Empirical Telemetry ──────────────────────────────────
    story.append(Paragraph("1. Empirical Telemetry: The Physical Breakdown of Model Alignment", styles["SectionHeader"]))
    story.append(Paragraph(
        "Stochastic LLMs cannot act as their own auditor. Comprehensive benchmark evaluations prove that model-internal "
        "guardrails collapse under realistic network conditions:",
        styles["BodyTextCustom"]
    ))

    # KPI Telemetry Matrix Table
    kpi_data = [
        [
            Paragraph("Empirical KPI Metric", styles["TableHead"]),
            Paragraph("Measured Value", styles["TableHead"]),
            Paragraph("Observed Failure Mode & Regulatory Impact", styles["TableHead"])
        ],
        [
            Paragraph("Overclaim Rate", styles["TableCellBold"]),
            Paragraph("<font color='#DC2626'><b>75.0%</b></font>", styles["TableCellBold"]),
            Paragraph("Agents assert action confirmation on trace-present baselines without physical wire proof (<i>DEMM-Bench, arXiv:2606.20634</i>).", styles["TableCellNormal"])
        ],
        [
            Paragraph("False Success Rate", styles["TableCellBold"]),
            Paragraph("<font color='#DC2626'><b>45.0%</b></font>", styles["TableCellBold"]),
            Paragraph("Harnesses emit successful execution receipts during simulated HTTP 504 timeouts (<i>n=200 empirical banking traces</i>).", styles["TableCellNormal"])
        ],
        [
            Paragraph("Duplicate Charge Risk", styles["TableCellBold"]),
            Paragraph("<font color='#DC2626'><b>100.0%</b></font>", styles["TableCellBold"]),
            Paragraph("Swallowed transport errors cause uncoordinated retries, producing duplicate wire transfers and ledger corruption.", styles["TableCellNormal"])
        ],
        [
            Paragraph("Wang–Huang State Space", styles["TableCellBold"]),
            Paragraph("<font color='#0284C7'><b>~10<sup>14.42</sup></b></font>", styles["TableCellBold"]),
            Paragraph("For 250 enterprise tools, internal evaluation coverage drops to <b>0.0000000002%</b>. Reward hacking is mathematically guaranteed.", styles["TableCellNormal"])
        ],
        [
            Paragraph("Boundary Collapse", styles["TableCellBold"]),
            Paragraph("<font color='#16A34A'><b>O(1)</b></font>", styles["TableCellBold"]),
            Paragraph("SovereignNexus collapses O(250<sup>3</sup>·2<sup>24</sup>) state explosion to an O(1) check per emitted wire mutation.", styles["TableCellNormal"])
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[120, 84, 300])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_secondary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.white),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (0, 4), (-1, 4), colors.white),
        ("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#F0FDF4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    # ── Section 2: Mathematical Foundation ──────────────────────────────
    story.append(Paragraph("2. The Mathematical Dilemma: The Wang–Huang Incompleteness Theorem", styles["SectionHeader"]))
    story.append(Paragraph(
        "In 2026, research by Wang & Huang established what is known as <i>Gödel’s Incompleteness Theorem for AI Agents</i> "
        "(arXiv:2603.28063): as tool count <i>K</i> and interaction horizon <i>H</i> expand, latent state-action space "
        "explodes combinatorially (<b>Ω = K<sup>H</sup> · 2<sup>D·H</sup></b>) while evaluation capacity <i>M</i> scales linearly. "
        "Coverage drops asymptotically to zero (<b>C = M/Ω → 0</b>). Model alignment is structurally incomplete.",
        styles["BodyTextCustom"]
    ))

    # =========================================================================
    # PAGE 2: Architectural Solution, 6-Disposition Membrane & Commercial CTA
    # =========================================================================
    story.append(PageBreak())

    story.append(Paragraph("3. The Architectural Solution: O(1) External Boundary Evaluation", styles["SectionHeader"]))
    story.append(Paragraph(
        "SovereignNexus resolves this mathematical paradox by completely abandoning internal prompt inspection. "
        "Instead, <code>smaos-audit</code> enforces an <b>out-of-band wire evaluation membrane</b> directly on physical silicon:",
        styles["BodyTextCustom"]
    ))

    # 6-Disposition Architecture Table
    disp_data = [
        [
            Paragraph("AEIB Disposition", styles["TableHead"]),
            Paragraph("Mathematical Trigger & Precedence", styles["TableHead"]),
            Paragraph("Enforced Runtime Safeguard (DORA / AI Act)", styles["TableHead"])
        ],
        [
            Paragraph("<b>INVALID_INPUT</b>", styles["TableCellBold"]),
            Paragraph("Precedence 1 • Non-canonical JCS / Schema violation", styles["TableCellNormal"]),
            Paragraph("Instant fail-closed drop before cryptographic evaluation.", styles["TableCellNormal"])
        ],
        [
            Paragraph("<b>UNKNOWN</b>", styles["TableCellBold"]),
            Paragraph("Precedence 2 • HTTP 504 Timeout / Transport carrier drop", styles["TableCellNormal"]),
            Paragraph("WireTruthReflector sets retry_held=true; halts false success.", styles["TableCellNormal"])
        ],
        [
            Paragraph("<b>MISSING_EVIDENCE</b>", styles["TableCellBold"]),
            Paragraph("Precedence 3 • Ed25519 signature / permit omitted", styles["TableCellNormal"]),
            Paragraph("Line stop; halts unauthenticated state mutation.", styles["TableCellNormal"])
        ],
        [
            Paragraph("<b>CONFLICT</b>", styles["TableCellBold"]),
            Paragraph("Precedence 4 • Contradictory policies or dual tokens", styles["TableCellNormal"]),
            Paragraph("Mandatory human escalation; execution locked.", styles["TableCellNormal"])
        ],
        [
            Paragraph("<b>REFUSED</b>", styles["TableCellBold"]),
            Paragraph("Precedence 5 • Regulatory invariant breach (CET1 < 10.5%)", styles["TableCellNormal"]),
            Paragraph("Autonomous Jidoka line stop; Three Exclusions Ledger minted.", styles["TableCellNormal"])
        ],
        [
            Paragraph("<b>CONFIRMED</b>", styles["TableCellBold"]),
            Paragraph("Precedence 6 • Bit-exact JCS hash match + Valid permit", styles["TableCellNormal"]),
            Paragraph("Execution permitted; RFC 9162 SCITT receipt committed.", styles["TableCellNormal"])
        ],
    ]
    disp_table = Table(disp_data, colWidths=[110, 180, 214])
    disp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_secondary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FEF3C7")), # Amber tint
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (0, 4), (-1, 4), colors.white),
        ("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#FEF2F2")), # Red tint
        ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#F0FDF4")), # Green tint
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(disp_table)
    story.append(Spacer(1, 10))

    # ── Section 4: Commercial CTA ───────────────────────────────────────
    cta_content = [
        [
            Paragraph("🎯 COMMERCIAL ENGAGEMENT: €1,500 / 5-DAY BOUNDED DIAGNOSTIC PILOT", styles["CtaTitle"])
        ],
        [
            Paragraph(
                "We provide enterprise CISOs and Board Risk Committees with definitive mathematical certainty "
                "before multi-agent swarms reach production environments. In 5 business days, we conduct a non-invasive, "
                "air-gapped forensic audit across your staging agent execution traces.",
                styles["CtaBody"]
            )
        ],
        [
            Paragraph(
                "<b>Audit Scope & Forensic Deliverables:</b><br/>"
                "• <b>250-Trace Diagnostic Scan:</b> Interrogation of 250 staging traces against the 6-disposition AEIB taxonomy.<br/>"
                "• <b>Toxic Receipt Gap Report:</b> Quantitative detection of HTTP 504 false-positive confirmations and double-spend exposure.<br/>"
                "• <b>DORA Article 17/28 Evidence Pack:</b> Automated generation of your initial vendor xBRL-CSV contribution pack.<br/>"
                "• <b>Air-Gapped Gate Deployment:</b> Pre-configured <code>smaos-verify</code> container running locally on your hardware.<br/>"
                "• <b>Executive Risk Presentation:</b> 30-minute CISO / Board briefing with reproducible terminal kill-shot proofs.<br/>"
                "<b>Commercial Terms:</b> Flat fee €1,500 • 5 business days • 100% On-Premises / Air-Gapped • Zero Cloud Egress.",
                styles["CtaBody"]
            )
        ],
        [
            Paragraph(
                "<b>To Schedule Diagnostic:</b> Contact Andrii Leukhin (Independent Researcher & Founder) at <b>andrejlo123@gmail.com</b> "
                "or connect on LinkedIn to reserve your pilot execution window.",
                styles["CtaBody"]
            )
        ]
    ]
    cta_table = Table(cta_content, colWidths=[504])
    cta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_cta_bg),
        ("BOX", (0, 0), (-1, -1), 1.5, c_cta_border),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 2), (-1, 2), 4),
    ]))
    story.append(cta_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ Generated 2-page executive PDF briefing: {filename}")

if __name__ == "__main__":
    out_file = "toxic-receipt-executive-briefing.pdf"
    if len(sys.argv) > 1:
        out_file = sys.argv[1]
    build_pdf(out_file)
