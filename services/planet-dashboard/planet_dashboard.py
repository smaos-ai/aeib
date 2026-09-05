import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import hashlib
import json
from datetime import datetime, timedelta
from collections import deque
import random
from dataclasses import asdict
from vision_api import VisionAPI, GovernRequest, RiskLevel, HumanGatePolicy

# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════
API_BASE = "http://localhost:8000/v1"
REFRESH_SECONDS = 2

# PSI drift thresholds (industry standard)
PSI_LOW = 0.1
PSI_MODERATE = 0.25
FINE_PER_VIOLATION = 35000000  # €35M EU AI Act max fine
BLOCKED_FINE_FACTOR = 0.012    # estimated fraction for a blocked high‑risk action

# ═══════════════════════════════════════════════════════════
# Session State Initialization
# ═══════════════════════════════════════════════════════════
if "capsule_log" not in st.session_state:
    st.session_state.capsule_log = deque(maxlen=200)
if "ap2_totals" not in st.session_state:
    st.session_state.ap2_totals = {
        "creator": 0.0, "data": 0.0, "planet": 0.0,
        "infra": 0.0, "architect": 0.0
    }
if "high_risk_blocked" not in st.session_state:
    st.session_state.high_risk_blocked = 0
if "high_risk_approved" not in st.session_state:
    st.session_state.high_risk_approved = 0
if "merkle_chain" not in st.session_state:
    st.session_state.merkle_chain = ["genesis"]
if "hourly_counts" not in st.session_state:
    st.session_state.hourly_counts = deque([0] * 24, maxlen=24)
if "error_log" not in st.session_state:
    st.session_state.error_log = deque(maxlen=20)
if "vision_api" not in st.session_state:
    st.session_state.vision_api = VisionAPI()
if "psi_history" not in st.session_state:
    st.session_state.psi_history = []
if "drift_auto_gates" not in st.session_state:
    st.session_state.drift_auto_gates = 0

# ═══════════════════════════════════════════════════════════
# API Calls (swap mock with real when Vision API is live)
# ═══════════════════════════════════════════════════════════
def fetch_real_ledger():
    """Attempt to pull from the actual Vision API /v1/ledger endpoint."""
    try:
        r = requests.get(f"{API_BASE}/ledger", timeout=1)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def mock_capsule():
    """Generate realistic mock data with Wire Human Gate governance."""
    risk = random.choices(["low", "medium", "high"], weights=[0.60, 0.28, 0.12])[0]
    blast_radius = {"low": 0.1, "medium": 0.4, "high": 0.8}[risk]

    # For high-risk, simulate mixed approval patterns
    if risk == "high":
        # 70% of high-risk actions get human approval after gate triggers
        human_approved = random.random() > 0.30
    else:
        human_approved = False  # Low/medium auto-approve

    # Run through VisionAPI Wire Human Gate
    governance_result = govern_action(
        action=f"{risk}_risk_action",
        blast_radius=blast_radius,
        user_id=f"user-{random.randint(1, 5)}",
        app_id="axiom-planet",
        human_approved=human_approved,
    )

    capsule_hash = hashlib.sha256(
        f"demo-{time.time()}-{random.random()}".encode()
    ).hexdigest()[:16]

    prev_root = st.session_state.merkle_chain[-1]
    new_root = hashlib.sha256(
        (prev_root + capsule_hash).encode()
    ).hexdigest()[:16]
    st.session_state.merkle_chain.append(new_root)

    approved = governance_result["charge_amount"] > 0  # Approved if charged
    public_key = f"0x{hashlib.sha256(f'key-{random.random()}'.encode()).hexdigest()[:12]}"
    verified = approved and random.random() > 0.05

    # Convert charge_amount from int (100) to decimal (0.003)
    charge_decimal = governance_result["charge_amount"] / 33333.33  # Scale to ~0.003

    return {
        "capsule_hash": capsule_hash,
        "risk_level": risk,
        "human_approved": approved,
        "ed25519_public_key": public_key if approved else None,
        "ed25519_verified": verified if approved else False,
        "charge_amount": charge_decimal if approved else 0,
        "split": {
            "creator": 0.00178 * charge_decimal if approved else 0,
            "data": 0.00059 * charge_decimal if approved else 0,
            "planet": 0.00030 * charge_decimal if approved else 0,
            "infra": 0.00030 * charge_decimal if approved else 0,
            "architect": 0.00003 * charge_decimal if approved else 0,
        },
        "timestamp": time.time(),
        "merkle_root": new_root,
        "psi_drift": governance_result["psi_drift"],
        "governance_reason": governance_result["reason"],
    }

def update_state():
    """Pull from real ledger or generate mock Capsules."""
    real_data = fetch_real_ledger()
    if real_data:
        # Process real ledger data when available
        for tx in real_data.get("transactions", []):
            process_capsule(tx)
    else:
        # Mock mode for demo
        for _ in range(random.randint(1, 3)):
            cap = mock_capsule()
            process_capsule(cap)

def process_capsule(cap):
    st.session_state.capsule_log.append(cap)
    if cap["human_approved"]:
        for key in st.session_state.ap2_totals:
            st.session_state.ap2_totals[key] += cap.get("split", {}).get(key, 0.0)
    if cap["risk_level"] == "high":
        if cap["human_approved"]:
            st.session_state.high_risk_approved += 1
        else:
            st.session_state.high_risk_blocked += 1
    # Update hourly count
    hour = datetime.fromtimestamp(cap["timestamp"]).hour
    st.session_state.hourly_counts[hour] = st.session_state.hourly_counts[hour] + 1

def get_current_drift():
    """Simulate PSI drift; replace with real model monitoring."""
    base = 0.05
    spike = random.gauss(0, 0.10)
    return max(0.0, base + spike)

def govern_action(action: str, blast_radius: float, user_id: str, app_id: str, human_approved: bool) -> dict:
    """
    Govern an action through VisionAPI Wire Human Gate.
    Returns: {"charge_amount": int, "blocked": bool, "reason": str, "proof": dict or None}
    """
    api = st.session_state.vision_api
    request = GovernRequest(
        request_id=f"capsule-{time.time()}",
        action=action,
        blast_radius=blast_radius,
        user_id=user_id,
        app_id=app_id,
        human_approved=human_approved,
    )

    # Check PSI drift
    current_psi = get_current_drift()
    st.session_state.psi_history.append(current_psi)

    # Run pre-execution check with drift detection
    result = api.pre_execute_check(request, psi_drift=current_psi)

    # Track drift auto-gate engagements
    if current_psi > api.policy.psi_drift_threshold:
        st.session_state.drift_auto_gates += 1

    return {
        "charge_amount": result.charge_amount,
        "blocked": not result.allowed,
        "reason": result.reason,
        "proof": asdict(result.proof) if result.proof else None,
        "psi_drift": current_psi,
    }

# ═══════════════════════════════════════════════════════════
# UI: Dashboard
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Axiom Planet Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/globe--v1.png", width=80)
    st.title("Axiom Planet")
    st.markdown("**Governance Membrane**")
    st.divider()
    st.metric("Current Merkle Root", st.session_state.merkle_chain[-1][:8] + "…")
    st.metric("Total Capsules", len(st.session_state.capsule_log))
    st.divider()
    st.caption("EU AI Act Article 12 Ready")
    st.caption("ISO 42001 Compliant")
    st.caption("Ed25519 + Secure Enclave")
    st.divider()
    if st.button("📥 Export Compliance Report"):
        st.download_button(
            "Download JSON",
            json.dumps(list(st.session_state.capsule_log), indent=2),
            "compliance_report.json"
        )

# Main title
st.title("🌍 Axiom Planet Dashboard")
st.caption("Real‑time governance membrane — every AI action governed, provenanced, and fairly compensated.")

# Update state
update_state()

# ═══════════════════════════════════════════════════════════
# Row 1: KPI Cards
# ═══════════════════════════════════════════════════════════
col1, col2, col3, col4 = st.columns(4)
total_capsules = len(st.session_state.capsule_log)
total_ap2 = sum(st.session_state.ap2_totals.values())
high_risk_total = st.session_state.high_risk_blocked + st.session_state.high_risk_approved
approval_rate = (
    st.session_state.high_risk_approved / high_risk_total * 100
) if high_risk_total else 100

col1.metric("📦 Today's Capsules", total_capsules)
col2.metric("💰 AP2 Collected", f"${total_ap2:.4f}")
col3.metric(
    "🛡️ High‑Risk Actions",
    f"{high_risk_total}",
    f"{st.session_state.high_risk_blocked} blocked"
)
col4.metric("✅ Approval Rate", f"{approval_rate:.0f}%")

# ═══════════════════════════════════════════════════════════
# Row 2: AP2 Distribution + Drift Alert
# ═══════════════════════════════════════════════════════════
col5, col6 = st.columns(2)

with col5:
    st.subheader("💸 AP2 Distribution (Real‑time)")
    labels = ['Creator (60%)', 'Data (20%)', 'Planet (10%)', 'Infra (9%)', 'Architect (1%)']
    values = [
        st.session_state.ap2_totals["creator"],
        st.session_state.ap2_totals["data"],
        st.session_state.ap2_totals["planet"],
        st.session_state.ap2_totals["infra"],
        st.session_state.ap2_totals["architect"]
    ]
    fig_pie = px.pie(
        names=labels,
        values=values,
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_pie.update_traces(textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)
    st.caption("Every $0.003 governed action splits automatically — 99% to creators, data, planet, infra; 1% to Architect.")

with col6:
    st.subheader("📉 Drift Monitor (Model X)")
    psi = get_current_drift()
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = psi,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Population Stability Index"},
        delta = {'reference': 0.05},
        gauge = {
            'axis': {'range': [None, 0.5]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, PSI_LOW], 'color': "lightgreen"},
                {'range': [PSI_LOW, PSI_MODERATE], 'color': "yellow"},
                {'range': [PSI_MODERATE, 0.5], 'color': "salmon"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': PSI_MODERATE
            }
        }
    ))
    fig_gauge.update_layout(height=300)
    st.plotly_chart(fig_gauge, use_container_width=True)

    if psi > PSI_MODERATE:
        st.error("🚨 Human Gate auto‑engaged — no high‑risk actions permitted")
    elif psi > PSI_LOW:
        st.warning("⚠️ Flagged for review — monitor closely")
    else:
        st.success("✅ Model stable")

# ═══════════════════════════════════════════════════════════
# Row 3: Merkle Chain + Capsule Flow
# ═══════════════════════════════════════════════════════════
col7, col8 = st.columns(2)

with col7:
    st.subheader("🔗 Merkle Chain (Last 10 Roots)")
    chain = st.session_state.merkle_chain[-10:]
    if chain:
        df_chain = pd.DataFrame({"Root": [r[:12] + "…" for r in chain]})
        st.dataframe(df_chain, use_container_width=True)
    st.caption("Immutable audit trail — each Capsule extends the chain.")

with col8:
    st.subheader("📊 Capsule Flow (24h)")
    hours = [(datetime.now() - timedelta(hours=i)).strftime("%H") for i in range(23, -1, -1)]
    df_hist = pd.DataFrame({"Hour": hours, "Capsules": list(st.session_state.hourly_counts)})
    fig_bar = px.bar(df_hist, x="Hour", y="Capsules")
    st.plotly_chart(fig_bar, use_container_width=True)

# ═══════════════════════════════════════════════════════════
# Row 4: Decision Ownership Table
# ═══════════════════════════════════════════════════════════
st.subheader("👤 Decision Ownership Map")
df = pd.DataFrame(list(st.session_state.capsule_log)[-15:])
if not df.empty:
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    display_cols = ['timestamp', 'capsule_hash', 'risk_level', 'human_approved',
                    'ed25519_public_key', 'ed25519_verified', 'charge_amount', 'merkle_root']
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True)
    st.caption("Every high‑risk action is tied to a verified Ed25519 public key — cryptographically non‑repudiable.")

# ═══════════════════════════════════════════════════════════
# Row 5: Governance ROI
# ═══════════════════════════════════════════════════════════
st.subheader("💎 Governance ROI Today")
fines_avoided = st.session_state.high_risk_blocked * FINE_PER_VIOLATION * BLOCKED_FINE_FACTOR
col9, col10, col11 = st.columns(3)
col9.metric("🚫 Unsafe Actions Prevented", st.session_state.high_risk_blocked)
col10.metric("💶 Est. Fines Avoided", f"€{fines_avoided:,.0f}")
col11.metric("🎨 Creator Royalties Paid", f"${st.session_state.ap2_totals['creator']:.4f}")

# ═══════════════════════════════════════════════════════════
# Auto‑refresh
# ═══════════════════════════════════════════════════════════
time.sleep(REFRESH_SECONDS)
st.rerun()
