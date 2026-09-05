
# SISS CMMC Level 2 Deployment Topology

## Air-Gapped Network Architecture


CMMC Level 2 Air-Gapped Deployment Topology
============================================

                     ┌─────────────────────────────────────────┐
                     │   EXTERNAL NETWORK (Internet)          │
                     └──────────────┬──────────────────────────┘
                                    │ [TLS 1.3 + MFA]
                     ┌──────────────▼──────────────────────────┐
                     │  EDGE BOUNDARY SEGMENT                  │
                     │  ├─ edge-0 (edge_gateway/TLS 1.3)      │
                     │  └─ edge-1 (remote_gateway/Suite B)    │
                     └──────────────┬──────────────────────────┘
                                    │ [Air-Gapped Firewall]
        ┌───────────────────────────┼────────────────────────────┐
        │                           │                            │
        │                    [INTERNAL NETWORK]                  │
        │     [No direct internet access from core nodes]        │
        │                                                         │
    ┌───▼─────────────────┐  ┌──────────────────┐  ┌──────────┐ │
    │ CONTROL PLANE       │  │  DATA PLANE      │  │ MONITOR  │ │
    │ (Isolated Segment)  │  │ (Isolated)       │  │ (Segment)│ │
    │                     │  │                  │  │          │ │
    │ ctl-0: gatekeeper  │  │ data-0: enclave │  │mon-0:OTel│ │
    │ ctl-1: job-router  │  │ data-1: auditor │  │mon-1:FW  │ │
    │ ctl-2: decision-db │  │                  │  │          │ │
    │                     │  │ [AES-256-GCM]    │  │ [TLS 1.3]│ │
    │ [TLS 1.3 + AEAD]    │  │ [Immutable Logs] │  │          │ │
    │ [Attestation]       │  │ [Attestation]    │  │[Anomaly  │ │
    └─────┬───────────────┘  └────────┬─────────┘  │ Detection│ │
          │                           │            └──────────┘ │
          │ [Internal VPN 1.3]        │[Seg Protocol]           │
          └───────────────┬───────────┘                         │
                          │                                     │
                    [Data Flow Control]                         │
                    [No Lateral Movement]                       │
                                                                │
└────────────────────────────────────────────────────────────────┘
        

## Network Statistics
- **Total Nodes:** 12
- **Network Segments:** 4
- **Minimum TLS Version:** 1.3
- **Encryption:** AES-256-GCM at-rest, TLS 1.3 in-transit

## Component Mapping
### Control Plane
- siss-gatekeeper: Access control policy enforcement
- siss-job-router: Task routing with latency validation
- siss-decision-db: Encrypted decision storage

### Data Plane
- siss-enclave: Cryptographic key storage and secrets
- siss-audit-archiver: Immutable audit logs (7-year retention)

### Monitoring & Boundary Protection
- siss-otel-tracer: Observability and anomaly detection
- siss-behavioral-firewall: Real-time threat detection
- Edge gateways: Network segmentation

---
Ready for Verifact/C3M audit review
