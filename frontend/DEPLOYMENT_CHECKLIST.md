# Pre-Deployment Checklist (Non-Negotiable)

## CODE QUALITY
- [ ] Linter passes: `npm run lint` (0 errors)
- [ ] Type check passes: `npx tsc --noEmit`
- [ ] Security scan: `npm audit` (0 high/critical)
- [ ] Code reviewed by 2+ people

## TESTING
- [ ] Unit tests pass: `npm test`
- [ ] E2E tests pass: `npm run test:e2e` (all 10 runs consistent)
- [ ] Load test passes: `k6 run tests/load/stress.js` (p95 <500ms)
- [ ] No memory leaks: Monitor DevTools Memory tab

## FUNCTIONALITY
- [ ] Form inputs work
- [ ] Submit button triggers classification
- [ ] Veto card appears for HIGH-RISK
- [ ] Authorize button signs and records
- [ ] Receipt appears in right pane
- [ ] Veto card disappears after authorization
- [ ] Kill switch works

## VISUAL
- [ ] No console errors (F12 → Console)
- [ ] UI renders correctly (all 3 panes visible)
- [ ] Buttons are clickable (not obscured)
- [ ] Responsive on mobile (DevTools → Device toolbar)

## DATA & DEPENDENCIES
- [ ] No hardcoded secrets in code
- [ ] All imports resolve (npm run build succeeds)
- [ ] CryptoKey signing works (Ed25519 + ECDSA fallback)

## DEPLOYMENT SAFETY
- [ ] Feature flags configured (new features off by default)
- [ ] Error logging set up (console errors visible)
- [ ] Monitoring dashboard created
- [ ] Rollback plan documented

## STAGING VALIDATION
- [ ] Code deployed to staging (if available)
- [ ] Smoke tests pass on staging
- [ ] Manual QA testing completed
- [ ] Database backup taken (if prod data involved)

## FINAL SIGN-OFF
- [ ] All checklist items completed
- [ ] No known bugs
- [ ] Ready for production
- [ ] Deployed by: _________________ Date: _________
