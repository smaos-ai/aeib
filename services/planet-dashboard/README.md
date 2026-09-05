# Axiom Planet Dashboard

Real-time governance membrane for Axiom Protocol—visualizes AP2 settlement splits, decision ownership, Merkle chains, and governance ROI in real-time.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run planet_dashboard.py
```

Dashboard will open at `http://localhost:8501`

## Features

- **AP2 Distribution (Pie Chart):** 60% creators, 20% data, 10% planet, 9% infra, 1% architect
- **Decision Ownership Map:** Ed25519 public key per Capsule, verification status
- **Merkle Chain Visualizer:** Last 10 cryptographic roots
- **Capsule Flow:** 24-hour histogram of governance decisions
- **PSI Drift Monitor:** Population Stability Index with auto-engage threshold (PSI > 0.25)
- **Governance ROI:** Fines prevented, creator royalties paid
- **Compliance Export:** Download full Capsule log as JSON

## Integration

Dashboard expects Vision API at `http://localhost:8000/v1/ledger`. Falls back to mock mode if unavailable.

## Development

- Mock mode: Generates realistic Capsule data with random risk levels
- Real mode: Pulls from Vision API ledger endpoint
- Auto-refresh every 2 seconds (configurable via `REFRESH_SECONDS`)
