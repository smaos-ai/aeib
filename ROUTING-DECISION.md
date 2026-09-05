# Routing Architecture Decision: Hybrid Qwen + Claude

**Decision Date:** Aug 31, 2026  
**Decision:** Implement hybrid policy routing for Sep 5-15 dev pilots

## Architecture

```
User Request
    ↓
Qwen 32B (FreeToken local)
    ↓ (policy classification)
    ├─ Confidence ≥85% → APPROVE/REJECT (local)
    ├─ Confidence 70-84% → ESCALATE to Claude
    └─ Confidence <70% → REJECT (too uncertain)
        ↓ (escalation)
    Claude API (fallback)
        ↓
        └─ Final decision + citation
```

## Benefits

| Dimension | Qwen-Only | Claude-Only | **Hybrid** |
|-----------|-----------|-------------|-----------|
| Cost | $0 | ~$0.003/req | ~$0.0005/req (80% local) |
| Latency | ~2s | ~1.5s | ~2s (stays local) |
| Data Privacy | ✅ Local only | ❌ Sent to API | ✅ Local-first |
| Reasoning Quality | ~87% accuracy | ~95% accuracy | ~92% (Qwen handles 80%) |
| Compliance Mapping | Good | Excellent | Good + Excellent |

## Thresholds

- **≥85% confidence** (Qwen) → Local decision (no Claude call)
- **70-84% confidence** → Escalate to Claude for verification
- **<70% confidence** → Reject as too uncertain

## Metrics to Track

For each pilot:
- % routed locally (target: 80%+)
- % escalated to Claude (target: 15-20%)
- % rejected as too uncertain (target: <5%)
- Cost per decision (target: <$0.001)
- Accuracy vs ground truth (target: 90%+)

## Implementation Timeline

- **Sep 5-7:** Update Stream A policy router to add Qwen fallback
- **Sep 8-15:** Dev pilots use hybrid routing
- **Sep 22+:** Production pilots (pilot with measured accuracy, adjust thresholds)

---

**Approved by:** User decision (Aug 31, 2026)
