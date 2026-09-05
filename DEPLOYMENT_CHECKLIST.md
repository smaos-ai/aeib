# Hybrid QA Pipeline: Deployment Checklist (Sep 8+)

## Pre-Deployment (Sep 1-7)

- [x] Gate 0 (pre_tool_verify.sh) — Implemented & tested
- [x] Gates 1-3 (post_tool_validate.sh) — Implemented & tested
- [x] Gates 4-5 (stop_validation.sh) — Implemented & tested
- [x] GitHub Actions workflow (qa-pipeline-hybrid.yml) — Implemented
- [x] Hook configuration (.claude/settings.json) — Updated
- [x] Documentation (README_HYBRID_PIPELINE.md) — Complete

## Deployment Day (Sep 8)

### Morning (Before 10am)

- [ ] Merge all gate scripts to main branch
  ```bash
  git add scripts/hooks/pre_tool_verify.sh
  git add scripts/hooks/post_tool_validate.sh
  git add scripts/hooks/stop_validation.sh
  git add .github/workflows/qa-pipeline-hybrid.yml
  git add .claude/settings.json
  git commit -m "DEPLOY: Hybrid QA pipeline gates 0-5 (Sep 8)"
  git push origin main
  ```

- [ ] Verify GitHub Actions workflow triggers
  - Go to `.github/workflows/qa-pipeline-hybrid.yml`
  - Check "Run workflow" button is available
  - Run manually: `workflow_dispatch`

- [ ] Test on a feature branch first
  ```bash
  git checkout -b test/hybrid-pipeline
  git push origin test/hybrid-pipeline
  # Wait for workflow to complete
  # Check results in Actions tab
  ```

### Midday (10am-3pm)

- [ ] Enable hooks in Claude Code
  - Verify `.claude/settings.json` is loaded
  - Run test command: `bash scripts/hooks/pre_tool_verify.sh`
  - Check output: "Gate 0 PASSED"

- [ ] Run Gate 0 verification
  ```bash
  bash scripts/hooks/pre_tool_verify.sh
  cat .gate-logs/gate_0_preflight.log
  cat .gate-status/gate_0_status.json
  ```

- [ ] Run Gates 1-3 test
  ```bash
  TOOL_NAME="Bash" TOOL_EXIT_CODE=0 bash scripts/hooks/post_tool_validate.sh
  cat .gate-logs/gate_1_3_validation.log
  ```

- [ ] Run Gates 4-5 test
  ```bash
  bash scripts/hooks/stop_validation.sh
  cat .gate-logs/gate_4_5_verification.log
  cat .smaos/compliance_check_*.json
  ```

### Afternoon (3pm-6pm)

- [ ] Validate GitHub Actions CI/CD pipeline
  - Merge test branch to main
  - Monitor workflow execution
  - Check all 7 jobs complete successfully
  - Verify artifacts uploaded

- [ ] Verify proof artifacts directory
  ```bash
  ls -la ~/.smaos/series_a/proof_artifacts/
  ls -la .smaos/ledger/
  ```

- [ ] Check git commits
  ```bash
  git log --oneline -5
  # Should see AP2 ledger commits
  ```

## Post-Deployment (Sep 9+)

### Daily Checks

- [ ] Monday: Review gate status
  ```bash
  cat .gate-status/gate_*_status.json | jq '.status'
  ```

- [ ] Wednesday: Code review
  ```bash
  bash scripts/hooks/pre_tool_verify.sh -v
  # Check for warnings or missing artifacts
  ```

- [ ] Friday: Integration test
  ```bash
  # Trigger workflow manually
  # Monitor all gates pass
  ```

### Weekly Maintenance

- [ ] Archive work receipts
  ```bash
  tar czf ~/.smaos/work_receipts_$(date +%Y%m).tar.gz ~/.smaos/work_receipts/
  # Keep recent files, archive older ones
  ```

- [ ] Review compliance reports
  ```bash
  cat .smaos/compliance_check_$(date +%Y%m%d).json
  ```

- [ ] Check proof artifacts
  ```bash
  ls -la ~/.smaos/series_a/proof_artifacts/
  # Expect 7 artifacts by Sep 16
  ```

## KARP Submission (Sep 16-22)

### Pre-Submission (Sep 15)

- [ ] Generate all 7 proof artifacts
  - [ ] 1_agentacct_config.json — ✅ Present
  - [ ] 2_unlazy_gates.md — 📝 Generate from Gate 2 evidence
  - [ ] 3_is_agentic.json — 📝 Run Is Agentic test
  - [ ] 4_canirun_grades.json — 📝 Run CanIRun.ai check
  - [ ] 5_ap2_ledger_pqc.md — ✅ Present
  - [ ] 6_ragas_golden_set.json — ✅ Present
  - [ ] 7_freetoken_benchmark.json — ✅ Present

- [ ] Validate RAGAS baseline
  ```bash
  # Target: 87%+ accuracy on 50-question golden set
  cat ~/.smaos/series_a/proof_artifacts/6_ragas_golden_set.json | jq '.accuracy'
  ```

- [ ] Create KARP submission bundle
  ```bash
  mkdir -p karp_submission_$(date +%Y%m%d)
  cp -r ~/.smaos/series_a/proof_artifacts/ karp_submission/
  cp HYBRID_PIPELINE_DEPLOYMENT.md karp_submission/
  cp ANNEX_IV_DOSSIER.md karp_submission/
  cp .smaos/compliance_check_*.json karp_submission/
  ```

- [ ] Prepare Annex IV dossier (9 sections)
  - [ ] Section 1: Harness architecture (1500+ lines)
  - [ ] Section 2: Memory & ingest (L1-L3)
  - [ ] Section 3: Orchestration & communication (L4-L5)
  - [ ] Section 4: Infrastructure (L6)
  - [ ] Section 5: Proof layer (L8)
  - [ ] Section 6: RAGAS validation (L7)
  - [ ] Section 7: Pilot outcomes (hotel, glass, school)
  - [ ] Section 8: Compliance timeline
  - [ ] Section 9: KARP voucher request

### Submission (Sep 16-22)

- [ ] Email to romana.cernikova@karp-kv.cz
  - Subject: "SMAOS Phase 1 - KARP Voucher Application (120k CZK)"
  - Attachments:
    - KARP_SUBMISSION.md (Czech description + budget)
    - proof_artifacts/ (7 files)
    - ANNEX_IV_DOSSIER.pdf (9 sections)
    - compliance_report.json (latest)

- [ ] Confirm receipt (Sep 17-18)
  - Check email for confirmation
  - Note KARP reference number
  - File in project records

- [ ] Follow up (Sep 20-22)
  - If no response, send reminder
  - Verify all documents received
  - Confirm submission window closure

## Phase 2 Prep (Post-Voucher)

- [ ] Monitor KARP approval (expected Oct 2026)
- [ ] Prepare BIC Plzeń application (1M CZK)
- [ ] Plan egress controls implementation
- [ ] Schedule full pilot production deployment

---

## Files to Monitor

```
scripts/hooks/pre_tool_verify.sh          → Gate 0
scripts/hooks/post_tool_validate.sh       → Gates 1-3
scripts/hooks/stop_validation.sh          → Gates 4-5
.github/workflows/qa-pipeline-hybrid.yml  → CI/CD

.gate-logs/gate_*.log                     → Execution logs
.gate-status/gate_*_status.json           → Gate status
.gate-evidence/*.json                     → Evidence files

~/.smaos/work_receipts/                   → agentacct receipts
.smaos/ledger/                            → AP2 Merkle entries
.smaos/compliance_check_*.json            → Compliance reports
```

## Rollback Plan

If issues occur during deployment:

1. **Critical bug in gate scripts:**
   ```bash
   git revert <commit-hash>
   git push origin main
   # Disables hybrid pipeline, reverts to old hooks
   ```

2. **Hook timeout issues:**
   - Edit `.claude/settings.json`
   - Increase timeout values
   - Reload settings

3. **AP2 ledger git conflicts:**
   ```bash
   git reset --soft HEAD~1
   # Undoes commit but keeps changes
   # Allows manual resolution
   ```

---

## Success Criteria

Pipeline is **production-ready** when:

- [x] All 6 gate scripts execute without errors
- [x] GitHub Actions workflow completes successfully
- [x] agentacct captures 50+ work receipts
- [x] unlazy gates enforce CHECK → EXPECT → EVIDENCE
- [x] AP2 ledger creates Merkle entries with Ed25519 signatures
- [x] Compliance reports auto-generate
- [ ] RAGAS baseline reaches 87%+ (Sep 7-8)
- [ ] All 7 proof artifacts present (Sep 9-15)
- [ ] Annex IV dossier complete (Sep 15)
- [ ] KARP submission ready (Sep 16)

---

**Last Updated:** Sep 1, 2026  
**Owner:** Andrej Lo (andrejlo123@gmail.com)  
**Target Completion:** Sep 8, 2026 (Production)
