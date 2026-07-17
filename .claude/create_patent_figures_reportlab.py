#!/usr/bin/env python3
"""
Patent Figures Generator (Stream P1) - Using ReportLab
Creates all 5 governance system figures in high-quality PDF format
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white, lightblue, lightgreen, yellow, red, green
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
import math

OUTPUT_DIR = "/Users/andriileukhin/Documents/SovereignNexus/.claude/"

def create_figure_1():
    """Figure 1: Merkle-DAG Audit Chain"""
    filename = f"{OUTPUT_DIR}Figure_1_Merkle_DAG.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, height - 0.5*inch, "Figure 1: Merkle-DAG Audit Chain (Append-Only)")

    # Node positions
    y_positions = [height - 2*inch, height - 4.5*inch, height - 7*inch]
    x = 1.5*inch

    c.setFont("Helvetica-Bold", 10)

    # Draw nodes
    nodes_data = [
        {
            'index': 1,
            'data': 'AI Decision A',
            'parent': 'None (Genesis)',
            'self_hash': 'SHA256(data_A)',
            'sig': 'ED25519(hash_1)'
        },
        {
            'index': 2,
            'data': 'AI Decision B',
            'parent': 'hash_1 ←',
            'self_hash': 'SHA256(hash_1 + data_B)',
            'sig': 'ED25519(hash_2)'
        },
        {
            'index': 3,
            'data': 'AI Decision C',
            'parent': 'hash_2 ←',
            'self_hash': 'SHA256(hash_2 + data_C)',
            'sig': 'ED25519(hash_3)'
        }
    ]

    for i, (y, node) in enumerate(zip(y_positions, nodes_data)):
        # Draw box
        c.setFillColor(HexColor("#FFFFE0"))
        c.setStrokeColor(black)
        c.setLineWidth(2)
        c.rect(x, y - 1.2*inch, 3.5*inch, 1.2*inch, fill=1)

        # Draw text
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 0.1*inch, y - 0.2*inch, f"Node {node['index']}")

        c.setFont("Helvetica", 7)
        c.drawString(x + 0.1*inch, y - 0.4*inch, f"Data: {node['data']}")
        c.drawString(x + 0.1*inch, y - 0.55*inch, f"Parent: {node['parent']}")
        c.drawString(x + 0.1*inch, y - 0.7*inch, f"Self: {node['self_hash']}")
        c.drawString(x + 0.1*inch, y - 0.85*inch, f"Sig: {node['sig']}")

        # Draw arrow to next node
        if i < 2:
            arrow_x = x + 1.75*inch
            c.setStrokeColor(HexColor("#00008B"))
            c.setLineWidth(2)
            c.line(arrow_x, y - 1.3*inch, arrow_x, y_positions[i+1] + 1.2*inch)

    # Immutability callout
    c.setFillColor(HexColor("#FFE4E1"))
    c.setStrokeColor(HexColor("#8B0000"))
    c.setLineWidth(2)
    c.rect(5.5*inch, 3*inch, 4*inch, 2*inch, fill=1)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#8B0000"))
    c.drawString(5.7*inch, 4.7*inch, "IMMUTABILITY GUARANTEE")

    c.setFont("Helvetica", 8)
    c.drawString(5.7*inch, 4.3*inch, "Changing Node 1 invalidates")
    c.drawString(5.7*inch, 4.0*inch, "all subsequent nodes")

    # Footer
    c.setFillColor(HexColor("#90EE90"))
    c.setStrokeColor(HexColor("#006400"))
    c.setLineWidth(1.5)
    c.rect(0.5*inch, 0.3*inch, 9*inch, 0.8*inch, fill=1)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(HexColor("#006400"))
    c.drawString(0.7*inch, 0.6*inch, "✓ Append-Only Chain: Each node cryptographically commits to its parent")

    c.save()
    print(f"✓ Figure 1: {filename}")


def create_figure_2():
    """Figure 2: Pre-Execution Governance Gate"""
    filename = f"{OUTPUT_DIR}Figure_2_Governance_Gate.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, height - 0.5*inch, "Figure 2: Pre-Execution Governance Gate (Fail-Closed)")

    # Gates
    gates = [
        {'num': 1, 'title': 'Known System?', 'desc': 'Is this AI trusted?', 'y': 9},
        {'num': 2, 'title': 'Fresh?', 'desc': 'Temporal decay check', 'y': 7.3},
        {'num': 3, 'title': 'Merkle Commit', 'desc': 'Append to audit chain', 'y': 5.6},
        {'num': 4, 'title': 'N-1 Consensus', 'desc': 'Get validator votes', 'y': 3.9},
        {'num': 5, 'title': 'Sign Decision', 'desc': 'ED25519 signature', 'y': 2.2},
    ]

    x = 1.5*inch

    c.setFillColor(HexColor("#ADD8E6"))
    c.setStrokeColor(HexColor("#000080"))
    c.setLineWidth(2)

    for i, gate in enumerate(gates):
        y = height - gate['y']*inch
        c.rect(x, y, 4*inch, 0.9*inch, fill=1)

        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 0.1*inch, y + 0.55*inch, f"Gate {gate['num']}: {gate['title']}")

        c.setFont("Helvetica-Oblique", 8)
        c.drawString(x + 0.1*inch, y + 0.25*inch, gate['desc'])

        # Arrow to next gate
        if i < 4:
            next_y = height - gates[i+1]['y']*inch
            arrow_x = x + 2*inch
            c.setStrokeColor(HexColor("#00008B"))
            c.setLineWidth(2)
            c.line(arrow_x, y, arrow_x, next_y + 0.9*inch)

    # Gate 4 validator details
    c.setFont("Helvetica", 7)
    c.drawString(7.5*inch, height - 4*inch, "Val 1: ✓  Val 2: ✓")
    c.drawString(7.5*inch, height - 4.15*inch, "Val 3: ✗  Val 4: ✓  Val 5: ✓")
    c.drawString(7.5*inch, height - 4.3*inch, "Result: 4/5 ≥ 4")

    # Success box (green)
    c.setFillColor(HexColor("#90EE90"))
    c.setStrokeColor(HexColor("#006400"))
    c.setLineWidth(2)
    c.rect(x, height - 10.2*inch, 4*inch, 0.7*inch, fill=1)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#006400"))
    c.drawString(x + 0.2*inch, height - 9.85*inch, "✓ EXECUTE ACTION")

    # Fail-closed rule
    c.setFillColor(HexColor("#FFFFE0"))
    c.setStrokeColor(HexColor("#8B0000"))
    c.setLineWidth(1.5)
    c.setDash([3, 3])
    c.rect(0.3*inch, height - 10.8*inch, 9.4*inch, 0.6*inch, fill=1)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(HexColor("#8B0000"))
    c.drawString(0.5*inch, height - 10.5*inch, "FAIL-CLOSED: If ANY gate fails → REJECT (default DENY)")

    c.save()
    print(f"✓ Figure 2: {filename}")


def create_figure_3():
    """Figure 3: Swarm Consensus Voting"""
    filename = f"{OUTPUT_DIR}Figure_3_Swarm_Consensus.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, height - 0.5*inch, "Figure 3: Swarm Consensus Voting (N-1 Byzantine)")

    # Decision hash at top
    c.setFont("Helvetica-Bold", 10)
    c.drawString(4*inch, height - 1.5*inch, "Decision Hash")

    # Validators in circle
    center_x = 5*inch
    center_y = height - 4*inch
    radius = 1.5*inch

    validators = [
        {'num': 1, 'vote': '✓ APPROVE'},
        {'num': 2, 'vote': '✓ APPROVE'},
        {'num': 3, 'vote': '✗ REJECT'},
        {'num': 4, 'vote': '✓ APPROVE'},
        {'num': 5, 'vote': '✓ APPROVE'},
    ]

    angles = [0, 72, 144, 216, 288]

    for validator, angle_deg in zip(validators, angles):
        angle = math.radians(angle_deg)
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)

        # Validator circle
        c.setStrokeColor(black)
        c.setLineWidth(1.5)
        color = HexColor("#90EE90") if '✓' in validator['vote'] else HexColor("#FFE4E1")
        c.setFillColor(color)
        c.circle(x, y, 0.35*inch, fill=1)

        c.setFont("Helvetica-Bold", 8)
        c.drawString(x - 0.2*inch, y + 0.15*inch, f"Val {validator['num']}")

        c.setFont("Helvetica", 7)
        c.drawString(x - 0.25*inch, y - 0.15*inch, validator['vote'])

        # Arrow to center
        c.setStrokeColor(HexColor("#000080"))
        c.setLineWidth(1.5)
        dx = center_x - x
        dy = center_y - y
        norm = math.sqrt(dx**2 + dy**2)
        start_x = x + 0.35*inch * dx / norm
        start_y = y + 0.35*inch * dy / norm
        c.line(start_x, start_y, center_x, center_y)

    # Central vote count box
    c.setFillColor(HexColor("#F0F8FF"))
    c.setStrokeColor(HexColor("#00008B"))
    c.setLineWidth(2)
    c.rect(center_x - 1.5*inch, center_y - 0.65*inch, 3*inch, 1.3*inch, fill=1)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(center_x - 1.3*inch, center_y + 0.35*inch, "VOTE COUNT")

    c.setFont("Helvetica", 8)
    c.drawString(center_x - 1.3*inch, center_y + 0.05*inch, "4/5 Votes")
    c.drawString(center_x - 1.3*inch, center_y - 0.25*inch, "≥ N-1 (4)?  YES ✓")

    # Byzantine tolerance info
    c.setFillColor(HexColor("#E6E6FA"))
    c.setStrokeColor(HexColor("#000080"))
    c.setLineWidth(1.5)
    c.rect(0.5*inch, height - 8.5*inch, 9*inch, 1.8*inch, fill=1)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#00008B"))
    c.drawString(0.7*inch, height - 7.2*inch, "N-1 BYZANTINE FAULT TOLERANCE")

    c.setFont("Helvetica", 8)
    c.drawString(0.7*inch, height - 7.5*inch, "N validators: 5 | Votes required: 4 | Security: Safe if ≤1 compromised")
    c.drawString(0.7*inch, height - 7.8*inch, "Failure: 3 or fewer approvals → REJECT")

    c.save()
    print(f"✓ Figure 3: {filename}")


def create_figure_4():
    """Figure 4: Temporal Decay Risk Scoring"""
    filename = f"{OUTPUT_DIR}Figure_4_Temporal_Decay.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1.5*inch, height - 0.5*inch, "Figure 4: Temporal Decay Risk Scoring")

    # Draw axes
    c.setStrokeColor(black)
    c.setLineWidth(2)

    x_start = 1*inch
    y_start = 2*inch
    x_end = 6*inch
    y_end = 8*inch

    # X and Y axes
    c.line(x_start, y_start, x_end, y_start)  # X-axis
    c.line(x_start, y_start, x_start, y_end)  # Y-axis

    # Axis labels
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_end + 0.2*inch, y_start, "Time (hours)")
    c.drawString(x_start - 0.8*inch, y_end, "Confidence (%)")

    # Axis ticks and labels
    c.setFont("Helvetica", 8)
    for i in range(0, 7):
        x_pos = x_start + (x_end - x_start) * i / 6
        c.line(x_pos, y_start - 0.15*inch, x_pos, y_start)
        c.drawString(x_pos - 0.1*inch, y_start - 0.35*inch, str(i))

    for i in range(0, 101, 25):
        y_pos = y_start + (y_end - y_start) * i / 100
        c.line(x_start - 0.15*inch, y_pos, x_start, y_pos)
        c.drawString(x_start - 0.45*inch, y_pos - 0.1*inch, f"{i}%")

    # Draw decay curve
    c.setStrokeColor(HexColor("#0000FF"))
    c.setLineWidth(2)

    points = []
    for t in range(0, 61):
        t_hours = t / 10.0
        confidence = 100 * math.exp(-t_hours / 1.0)
        x = x_start + (x_end - x_start) * t_hours / 6
        y = y_start + (y_end - y_start) * confidence / 100
        points.append((x, y))

    for i in range(len(points) - 1):
        c.line(points[i][0], points[i][1], points[i+1][0], points[i+1][1])

    # Threshold line (red)
    threshold_y = y_start + (y_end - y_start) * 10 / 100
    c.setStrokeColor(HexColor("#FF0000"))
    c.setLineWidth(2.5)
    c.setDash([5, 5])
    c.line(x_start, threshold_y, x_end, threshold_y)
    c.setDash([])

    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_end + 0.2*inch, threshold_y, "REJECT (10%)")

    # ACCEPT zone
    c.setFillColor(HexColor("#90EE90"))
    c.setFillAlpha(0.2)
    c.rect(x_start, threshold_y, x_end - x_start, y_end - threshold_y, fill=1, stroke=0)

    c.setFillColor(HexColor("#006400"))
    c.setFillAlpha(1.0)
    c.drawString(x_start + 0.3*inch, y_end - 0.5*inch, "ACCEPT ZONE")

    # REJECT zone
    c.setFillColor(HexColor("#FFB6C1"))
    c.setFillAlpha(0.2)
    c.rect(x_start, y_start, x_end - x_start, threshold_y - y_start, fill=1, stroke=0)

    c.setFillColor(HexColor("#8B0000"))
    c.setFillAlpha(1.0)
    c.drawString(x_end - 0.8*inch, y_start + 0.3*inch, "REJECT ZONE")

    # Example points
    # 5h old
    age_5h_conf = 100 * math.exp(-5)
    x_5h = x_start + (x_end - x_start) * 5 / 6
    y_5h = y_start + (y_end - y_start) * age_5h_conf / 100

    c.setFillColor(HexColor("#FF0000"))
    c.circle(x_5h, y_5h, 0.1*inch, fill=1)
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#8B0000"))
    c.drawString(x_5h + 0.15*inch, y_5h, f"5h: {age_5h_conf:.2f}%")

    # 30 min old
    age_30m_conf = 100 * math.exp(-0.5)
    x_30m = x_start + (x_end - x_start) * 0.5 / 6
    y_30m = y_start + (y_end - y_start) * age_30m_conf / 100

    c.setFillColor(HexColor("#00AA00"))
    c.circle(x_30m, y_30m, 0.1*inch, fill=1)
    c.setFillColor(HexColor("#006400"))
    c.drawString(x_30m - 0.5*inch, y_30m + 0.2*inch, f"30m: {age_30m_conf:.1f}%")

    # Formula
    c.setFont("Helvetica", 8)
    c.drawString(1.5*inch, 1.5*inch, "Formula: C(t) = 100 × e^(-t/λ), where λ=1 hour")

    c.save()
    print(f"✓ Figure 4: {filename}")


def create_figure_5():
    """Figure 5: End-to-End System Architecture"""
    filename = f"{OUTPUT_DIR}Figure_5_System_Architecture.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, height - 0.5*inch, "Figure 5: End-to-End System Architecture")

    y_pos = height - 1.2*inch

    # INPUT LAYER
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#000080"))
    c.drawString(1*inch, y_pos, "INPUT LAYER")

    y_pos -= 0.5*inch

    # Input models
    models = [
        (1.3*inch, 'AI Model 1\n(Decision A)'),
        (3.8*inch, 'AI Model 2\n(Decision B)'),
        (6.3*inch, 'AI Model N\n(Decision C)'),
    ]

    for x, label in models:
        c.setFillColor(HexColor("#E0FFFF"))
        c.setStrokeColor(HexColor("#000080"))
        c.setLineWidth(1.5)
        c.rect(x, y_pos - 0.6*inch, 1.4*inch, 0.6*inch, fill=1)

        c.setFont("Helvetica", 7)
        c.drawString(x + 0.1*inch, y_pos - 0.25*inch, label)

    y_pos -= 1*inch

    # Processing stages
    stages = [
        ('GOVERNANCE GATE VALIDATION', ['Known AI Check', 'Temporal Decay', 'Replay Detection']),
        ('MERKLE-DAG AUDIT CHAIN', ['Append Decision', 'Compute Hashes', 'Store Immutably']),
        ('SWARM CONSENSUS VALIDATION', ['Validator Voting', 'Check N-1', '4/5 PASS']),
        ('CRYPTOGRAPHIC ATTESTATION', ['Sign ED25519', 'Generate Signature', 'Attach Record']),
    ]

    for stage_title, items in stages:
        c.setFillColor(HexColor("#F0F8FF"))
        c.setStrokeColor(HexColor("#00008B"))
        c.setLineWidth(1.5)
        c.rect(1*inch, y_pos - 0.85*inch, 6.5*inch, 0.9*inch, fill=1)

        c.setFont("Helvetica-Bold", 8)
        c.drawString(1.2*inch, y_pos - 0.15*inch, stage_title)

        c.setFont("Helvetica", 6)
        items_str = ' | '.join(items)
        c.drawString(1.2*inch, y_pos - 0.4*inch, items_str)

        # Arrow between stages
        c.setStrokeColor(HexColor("#00008B"))
        c.setLineWidth(2)
        c.line(4.25*inch, y_pos - 0.95*inch, 4.25*inch, y_pos - 1.1*inch)

        y_pos -= 1.2*inch

    # OUTPUT LAYER
    y_pos -= 0.3*inch
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#006400"))
    c.drawString(1*inch, y_pos, "OUTPUT LAYER")

    y_pos -= 0.5*inch

    # Output actions
    actions = [
        (1.3*inch, 'Action A\nExecuted ✓\n+ Proof'),
        (3.8*inch, 'Action B\nExecuted ✓\n+ Proof'),
        (6.3*inch, 'Action C\nExecuted ✓\n+ Proof'),
    ]

    for x, label in actions:
        c.setFillColor(HexColor("#90EE90"))
        c.setStrokeColor(HexColor("#006400"))
        c.setLineWidth(1.5)
        c.rect(x, y_pos - 0.85*inch, 1.4*inch, 0.85*inch, fill=1)

        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(HexColor("#006400"))
        c.drawString(x + 0.1*inch, y_pos - 0.35*inch, label)

    # Footer
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(HexColor("#000080"))
    c.drawString(1*inch, 0.5*inch, "Complete Pipeline: Merkle Proof + Ed25519 Signature + Validator Audit Trail")

    c.save()
    print(f"✓ Figure 5: {filename}")


def main():
    print("=" * 60)
    print("PATENT FIGURES GENERATOR (Stream P1)")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    try:
        create_figure_1()
        create_figure_2()
        create_figure_3()
        create_figure_4()
        create_figure_5()

        print()
        print("=" * 60)
        print("ALL FIGURES CREATED SUCCESSFULLY")
        print("=" * 60)
        print()
        print("Files:")
        import os
        for i in range(1, 6):
            files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(f"Figure_{i}")]
            for f in files:
                full_path = os.path.join(OUTPUT_DIR, f)
                size_kb = os.path.getsize(full_path) / 1024
                print(f"  {full_path} ({size_kb:.1f} KB)")
        print()
        print("Ready for USPTO submission!")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
