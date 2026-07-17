# Creator SDK Phase 2: Creator Onboarding Guide
## "Author Your Own Governance Skill" Tutorial (30 min)

**Status:** Onboarding Program (Aug 1–30, 2026)  
**Target Audience:** Creators (compliance experts, engineers, risk officers)  
**Delivery Format:** Web tutorial + CLI tool + video guides  
**Time to First Skill:** 30 minutes  
**Quality Bar:** 8.5/10 (beginner-friendly, practical, well-tested)

---

## Welcome to Creator SDK Phase 2

You've been using SovereignNexus governance skills. Now **you can author your own.**

This guide teaches you to:
1. **Understand** the skill framework (10 min)
2. **Choose** a skill template (5 min)
3. **Implement** your first skill (10 min)
4. **Test & publish** to the marketplace (5 min)

By the end, you'll have authored a skill that other creators can use (and you'll earn 90% of its revenue).

---

## Part 1: Understand the Skill Framework (10 min)

### 1.1 What is a Skill?

A **skill** is a reusable governance module that audits, enforces, or enforces rules on the SovereignNexus platform.

**Examples:**
- **Settlement Verification:** Audit the 99/1 split in real-time
- **Fairness Auditor:** Detect bias in settlement logic
- **Custom Rate Limiter:** Enforce token budgets per creator
- **GDPR Erasure:** Handle data deletion requests
- **Approval Workflow:** Require sign-off before large payouts

**Key Principle:** Skills are **open-source, forkable, and auditable**. Creators own their governance code.

### 1.2 Skill Structure

Every skill has 3 parts:

**Part A: Metadata (SKILL.json)**
```json
{
  "id": "my-settlement-auditor",
  "name": "My Settlement Auditor",
  "description": "Custom settlement verification logic",
  "version": "1.0.0",
  "author": { "name": "Alice" },
  "governance": {
    "modifiable": true,
    "auditable": true
  }
}
```

**Part B: Implementation (index.ts)**
```typescript
export async function execute(context, input) {
  // Your logic here
  return { result: "..." };
}
```

**Part C: Tests (tests/index.test.ts)**
```typescript
describe('My Settlement Auditor', () => {
  it('should verify 99/1 split', () => {
    // Test code
  });
});
```

That's it. **No server, no deployment, no locks-in.** Just TypeScript.

### 1.3 Skill Governance Guarantees

When you author a skill, you attest to:
- ✅ **No data exfiltration** — skill doesn't steal data
- ✅ **No governance bypass** — skill doesn't hack the 99/1 split
- ✅ **No resource abuse** — skill respects timeout/memory limits
- ✅ **Open-source** — other creators can read, fork, improve your skill

See [Safety Checklist](#safety-checklist) below.

---

## Part 2: Choose Your Skill Template (5 min)

### 2.1 Five Templates to Choose From

**Template 1: Settlement Auditor** (Most Popular)
- **Use if:** You want to audit settlement logic or add custom validation
- **Example:** "Alert me if settlement_variance > 50%"
- **Time to implement:** 20 min
- **Revenue potential:** €500–€2K/month (if 100+ creators use it)

**Template 2: Rate Limiter**
- **Use if:** You want to enforce resource budgets (tokens, requests, etc.)
- **Example:** "Cap creators to 1M tokens/month"
- **Time to implement:** 15 min
- **Revenue potential:** €1K–€5K/month (enterprise adoption)

**Template 3: Compliance Auditor**
- **Use if:** You know GDPR, SOX, HIPAA, or other regulations
- **Example:** "Generate GDPR audit trail for EU regulators"
- **Time to implement:** 30 min
- **Revenue potential:** €2K–€10K/month (high-value use case)

**Template 4: Approval Workflow**
- **Use if:** You want to implement multi-party authorization
- **Example:** "Require 3-of-5 board approval for settlements > €10K"
- **Time to implement:** 25 min
- **Revenue potential:** €1K–€3K/month

**Template 5: Custom DSL Rule Engine**
- **Use if:** You want creators to define rules without code
- **Example:** "Create rules: if settlement > 1000 then require_approval"
- **Time to implement:** 45 min
- **Revenue potential:** €3K–€10K/month (very flexible)

### 2.2 Which Template Is Right for You?

**Ask yourself:**
1. **What problem do I solve?** (settlement auditing, rate limiting, compliance, approval, rules)
2. **How many creators have this problem?** (bigger market = higher revenue)
3. **How much time do I have?** (15 min → 45 min depending on complexity)

**Our Recommendation:**
- **First-time authors:** Start with Template 1 (Settlement Auditor)
  - Easy to implement
  - High demand (every creator needs settlement auditing)
  - Clear revenue path
- **Experienced authors:** Try Template 3 (Compliance Auditor)
  - Differentiated
  - Higher price point
  - Attracts enterprise customers

---

## Part 3: Implement Your First Skill (10 min)

### 3.1 Step 1: Create Skill Project Structure

**Download the Creator SDK:**
```bash
npm install @sovereignnexus/creator-sdk --save-dev
```

**Create your skill directory:**
```bash
mkdir my-settlement-auditor
cd my-settlement-auditor
npm init -y
npm install --save-dev typescript jest @sovereignnexus/creator-sdk
```

**Create project structure:**
```bash
mkdir src tests
touch SKILL.json src/index.ts tests/index.test.ts README.md safety-checklist.md
```

**Result:**
```
my-settlement-auditor/
├── SKILL.json                  # Metadata
├── src/
│   └── index.ts               # Your skill implementation
├── tests/
│   └── index.test.ts          # Unit tests
├── README.md                  # Documentation
├── safety-checklist.md        # Author attestation
└── package.json
```

### 3.2 Step 2: Write SKILL.json (2 min)

Copy this template and fill in your details:

```json
{
  "id": "my-settlement-auditor",
  "name": "My Settlement Auditor",
  "description": "Custom settlement verification skill that audits the 99/1 split and detects anomalies.",
  "version": "1.0.0",
  "author": {
    "type": "Creator",
    "name": "Your Name",
    "email": "you@example.com"
  },
  "targets": {
    "sdk_min_version": "1.0.0",
    "sdk_max_version": "*"
  },
  "governance": {
    "modifiable": true,
    "auditable": true,
    "versionable": true
  },
  "parameters": {
    "ap2_entry_id": {
      "type": "string",
      "description": "AP2 Entry UUID to audit",
      "required": true
    },
    "variance_threshold_pct": {
      "type": "number",
      "description": "Alert if variance exceeds this %",
      "required": false,
      "default": 10
    }
  },
  "pricing": {
    "model": "free",
    "base_price_usd": 0
  }
}
```

### 3.3 Step 3: Implement Your Skill Logic (5 min)

Copy this template and add your logic:

```typescript
// src/index.ts

import { SkillDefinition, SkillContext, SkillInput, SkillOutput } from '@sovereignnexus/creator-sdk';
import { AP2Entry } from '@sovereignnexus/creator-sdk';

export interface MyAuditorInput extends SkillInput {
  ap2_entry_id: string;
  variance_threshold_pct?: number;
}

export interface MyAuditorOutput extends SkillOutput {
  settlement_id: string;
  is_valid: boolean;
  issues: Array<{
    type: string;
    severity: 'ERROR' | 'WARNING' | 'INFO';
    message: string;
  }>;
}

export const mySettlementAuditorSkill: SkillDefinition = {
  id: 'my-settlement-auditor',
  name: 'My Settlement Auditor',
  description: 'Custom settlement verification skill',
  author: { type: 'Creator', name: 'Your Name' },
  version: '1.0.0',

  governance: {
    modifiable: true,
    auditable: true,
    versionable: true,
  },

  execute: async (
    context: SkillContext,
    input: MyAuditorInput
  ): Promise<MyAuditorOutput> => {
    const issues: any[] = [];
    const variance_threshold_pct = input.variance_threshold_pct || 10;

    try {
      // Step 1: Fetch the AP2 entry
      const ap2Entry = await context.ap2Ledger.get(input.ap2_entry_id);
      
      if (!ap2Entry) {
        throw new Error(`Entry not found: ${input.ap2_entry_id}`);
      }

      // Step 2: Verify 99/1 split
      const expected_steward = Math.floor(ap2Entry.total_microcents * 0.01);
      const actual_steward = ap2Entry.steward_payout;
      const difference = Math.abs(expected_steward - actual_steward);

      if (difference > 0) {
        issues.push({
          type: 'SPLIT_MISMATCH',
          severity: 'ERROR',
          message: `Steward payout mismatch: expected ${expected_steward}, got ${actual_steward}`,
        });
      }

      // Step 3: Check for anomalies (optional)
      // [TODO: Add your custom logic here]
      // Example: Detect if settlement amount is unusually high/low
      
      const avg_settlement = await context.metrics.getAverageSettlement(context.creatorId);
      const variance_pct = Math.abs(ap2Entry.total_microcents - avg_settlement) / avg_settlement * 100;

      if (variance_pct > variance_threshold_pct) {
        issues.push({
          type: 'VARIANCE_DETECTED',
          severity: 'WARNING',
          message: `Settlement variance ${variance_pct.toFixed(2)}% exceeds threshold ${variance_threshold_pct}%`,
        });
      }

      // Step 4: Return audit result
      return {
        settlement_id: ap2Entry.id,
        is_valid: issues.filter(i => i.severity === 'ERROR').length === 0,
        issues,
      };
    } catch (error) {
      context.logger.error(`Settlement audit failed: ${error.message}`);
      throw error;
    }
  },
};

// Export for marketplace
export default mySettlementAuditorSkill;
```

### 3.4 Step 4: Write Unit Tests (2 min)

Copy this template:

```typescript
// tests/index.test.ts

import { mySettlementAuditorSkill } from '../src/index';
import { SkillContext } from '@sovereignnexus/creator-sdk';

describe('My Settlement Auditor', () => {
  let mockContext: SkillContext;

  beforeEach(() => {
    // Mock the AP2 Ledger and metrics
    mockContext = {
      creatorId: 'creator-123',
      ap2Ledger: {
        get: jest.fn(),
      },
      metrics: {
        getAverageSettlement: jest.fn(),
      },
      logger: {
        error: jest.fn(),
      },
    } as any;
  });

  it('should pass valid 99/1 split', async () => {
    // Setup mock data
    mockContext.ap2Ledger.get.mockResolvedValue({
      id: 'ap2-123',
      total_microcents: 10000,
      steward_payout: 100,  // 1%
      beneficiary_payout: 9900, // 99%
    });

    mockContext.metrics.getAverageSettlement.mockResolvedValue(10000);

    // Execute skill
    const result = await mySettlementAuditorSkill.execute(mockContext, {
      ap2_entry_id: 'ap2-123',
      variance_threshold_pct: 10,
    });

    // Assert
    expect(result.is_valid).toBe(true);
    expect(result.issues.length).toBe(0);
  });

  it('should detect split mismatch', async () => {
    mockContext.ap2Ledger.get.mockResolvedValue({
      id: 'ap2-456',
      total_microcents: 10000,
      steward_payout: 500,  // 5% (wrong!)
      beneficiary_payout: 9500,
    });

    const result = await mySettlementAuditorSkill.execute(mockContext, {
      ap2_entry_id: 'ap2-456',
    });

    expect(result.is_valid).toBe(false);
    expect(result.issues).toContainEqual(
      expect.objectContaining({
        type: 'SPLIT_MISMATCH',
        severity: 'ERROR',
      })
    );
  });

  it('should detect variance anomaly', async () => {
    mockContext.ap2Ledger.get.mockResolvedValue({
      id: 'ap2-789',
      total_microcents: 100000,  // 10x normal
      steward_payout: 1000,
      beneficiary_payout: 99000,
    });

    mockContext.metrics.getAverageSettlement.mockResolvedValue(10000);

    const result = await mySettlementAuditorSkill.execute(mockContext, {
      ap2_entry_id: 'ap2-789',
      variance_threshold_pct: 10,
    });

    expect(result.issues).toContainEqual(
      expect.objectContaining({
        type: 'VARIANCE_DETECTED',
        severity: 'WARNING',
      })
    );
  });
});
```

### 3.5 Step 5: Run Tests

```bash
npm test
```

**Expected output:**
```
PASS  tests/index.test.ts
  My Settlement Auditor
    ✓ should pass valid 99/1 split (5ms)
    ✓ should detect split mismatch (3ms)
    ✓ should detect variance anomaly (4ms)

Test Suites: 1 passed, 1 total
Tests:       3 passed, 3 total
```

---

## Part 4: Test & Publish (5 min)

### 4.1 Step 1: Write Documentation (README.md)

```markdown
# My Settlement Auditor

## Overview
This skill audits settlement entries to ensure they comply with the 99/1 covenant. It detects split mismatches and anomalous settlement amounts.

## Features
- ✅ Verify 99/1 split ratio
- ✅ Detect settlement variance
- ✅ Generate audit trail
- ✅ Real-time alerts

## Installation
```bash
npm install my-settlement-auditor
```

## Usage
```typescript
const skillRegistry = new SkillRegistry();
const result = await skillRegistry.execute('my-settlement-auditor', {
  ap2_entry_id: 'ap2-123',
  variance_threshold_pct: 10
});

if (result.is_valid) {
  console.log('Settlement is valid!');
} else {
  console.log('Issues found:', result.issues);
}
```

## Parameters
- `ap2_entry_id` (required): AP2 Entry UUID
- `variance_threshold_pct` (optional): Alert if variance > this %. Default: 10%

## Output
```typescript
{
  settlement_id: string;
  is_valid: boolean;
  issues: Array<{
    type: string;
    severity: 'ERROR' | 'WARNING' | 'INFO';
    message: string;
  }>;
}
```

## Pricing
Free (0% revenue share)

## Support
Email: you@example.com
```

### 4.2 Step 2: Complete Safety Checklist

**Create `safety-checklist.md`:**

```markdown
# Safety Checklist

## Governance Integrity
- [x] My skill does NOT modify governance rules
- [x] My skill does NOT bypass covenant firewall
- [x] My skill does NOT change 99/1 split ratio
- [x] My skill only READS or AUDITS governance

## Data Exfiltration Prevention
- [x] My skill does NOT send data to external servers
- [x] My skill does NOT log PII
- [x] My skill respects data residency requirements

## Dependency Management
- [x] I have declared all dependencies
- [x] I have tested with SDK 1.0.0+
- [x] All dependencies are pinned

## Error Handling
- [x] My skill handles errors gracefully
- [x] No stack traces exposed to users
- [x] Clear error messages provided

## Testing & Documentation
- [x] Unit tests written (80%+ coverage)
- [x] README.md complete
- [x] 3+ usage examples provided

## Attestation
By checking all boxes, I attest that my skill meets all safety standards.

**Name:** Your Name  
**Date:** 2026-08-05  
**Signature:** (Your Name)
```

### 4.3 Step 3: Submit to Marketplace

**Via Web UI:**
1. Go to https://marketplace.sovereignnexus.ai/creators/me
2. Click "Submit New Skill"
3. Upload your skill directory as `.zip`
4. Fill in pricing, category, tags
5. Submit for review

**Via CLI (faster):**
```bash
npm install -g @sovereignnexus/cli

sns-cli skill publish . \
  --category settlement-verification \
  --pricing-model free \
  --author-name "Your Name"
```

### 4.4 Step 4: Watch Automated Validation

Platform validates:
- ✅ SKILL.json schema
- ✅ TypeScript compilation
- ✅ Unit tests pass
- ✅ Security scan (npm audit)
- ✅ Code coverage > 80%

**Status dashboard:**
```
Submission: sub-abc123
Status: VALIDATING

Checks:
  ✓ Schema validation (2s)
  ✓ TypeScript compilation (8s)
  ✓ Unit tests (12s) — 3/3 tests passed, 92% coverage
  ✓ Security audit (5s) — 0 vulnerabilities
  ✓ Linting (3s) — 0 issues

Next: Manual security review by Trail of Bits (~24 hours)
```

### 4.5 Step 5: Publish

Once approved:
```bash
sns-cli skill publish sub-abc123 --live
```

**Result:**
```
✓ Skill published!
Listing URL: https://marketplace.sovereignnexus.ai/skills/my-settlement-auditor
Start earning: Creators using your skill will send you 90% of skill revenue.
```

---

## Common Patterns & Examples

### Pattern 1: Settlement Variance Detector

**Use case:** Alert if a creator's settlement amount drops suddenly

```typescript
// Check if settlement is 30%+ lower than average
const variance_pct = (avg - actual) / avg * 100;
if (variance_pct > 30) {
  return {
    type: 'SETTLEMENT_DROP',
    severity: 'WARNING',
    message: `Settlement dropped ${variance_pct.toFixed(1)}%`
  };
}
```

### Pattern 2: High-Value Settlement Alert

**Use case:** Flag settlements above a threshold for review

```typescript
if (ap2Entry.total_microcents > 1_000_000) {
  return {
    type: 'HIGH_VALUE',
    severity: 'INFO',
    message: 'Settlement > €10,000. Flagged for audit.'
  };
}
```

### Pattern 3: Duplicate Settlement Detector

**Use case:** Find duplicate settlements (possible error)

```typescript
const recentSettlements = await context.ap2Ledger.queryRecent(
  context.creatorId,
  24 * 60 * 60  // Last 24 hours
);

const isDuplicate = recentSettlements.some(s =>
  s.total_microcents === ap2Entry.total_microcents &&
  s.timestamp === ap2Entry.timestamp
);

if (isDuplicate) {
  return {
    type: 'DUPLICATE_SETTLEMENT',
    severity: 'ERROR',
    message: 'Possible duplicate settlement detected'
  };
}
```

### Pattern 4: Custom Regex-Based Validation

**Use case:** Validate settlement metadata against custom rules

```typescript
const metadataPattern = /^[A-Z]{2}-\d{4}-[0-9a-f]{8}$/;
if (!metadataPattern.test(ap2Entry.metadata)) {
  return {
    type: 'METADATA_FORMAT_ERROR',
    severity: 'ERROR',
    message: 'Settlement metadata does not match expected format'
  };
}
```

---

## Safety Checklist (Detailed)

Before publishing, answer these questions:

### 1. Governance Integrity
- [ ] Does my skill read-only? (No mutations to ledger)
- [ ] Does it respect the 99/1 covenant?
- [ ] Does it use the authorized AP2Ledger API?
- [ ] Does it avoid bypassing covenant firewall?

### 2. Data Protection
- [ ] Does it access creator's private keys? (NO!)
- [ ] Does it log sensitive data? (NO!)
- [ ] Does it send data to external servers? (NO!)
- [ ] Does it respect `data_residency_required`?

### 3. Performance
- [ ] Does it complete within 5 seconds?
- [ ] Does it use < 256MB memory?
- [ ] Does it cache expensive queries?
- [ ] Does it batch API calls?

### 4. Error Handling
- [ ] Does it catch all exceptions?
- [ ] Does it provide user-friendly error messages?
- [ ] Does it log errors to audit trail (not external services)?
- [ ] Does it fail gracefully (no crashes)?

### 5. Testing
- [ ] Are unit tests passing?
- [ ] Is coverage > 80%?
- [ ] Are edge cases tested?
- [ ] Are error scenarios tested?

### 6. Documentation
- [ ] Is README.md comprehensive?
- [ ] Are parameters documented?
- [ ] Are outputs documented?
- [ ] Are usage examples provided?

### 7. Licensing & Attribution
- [ ] Do I use OSI-approved license (MIT/Apache/GPL)?
- [ ] Do I credit third-party code?
- [ ] Do I understand creators can fork my skill?
- [ ] Am I OK with open-source distribution?

### 8. Legal & Compliance
- [ ] Do I handle PII? (If yes, GDPR compliance required)
- [ ] Do I handle financial data? (If yes, SOX compliance)
- [ ] Do I violate any patents/IP?
- [ ] Have I disclosed any conflicts of interest?

---

## Troubleshooting

### Problem: Tests fail locally but pass on CI

**Solution:**
- Check for hardcoded file paths (use `path.join()`)
- Mock all external dependencies
- Ensure tests don't depend on execution order
- Run tests in isolation: `jest --testNamePattern="test name"`

### Problem: "SDK version mismatch" error on submission

**Solution:**
- Check that `sdk_min_version` in SKILL.json matches installed SDK
- Update: `npm update @sovereignnexus/creator-sdk`
- Verify: `npm list @sovereignnexus/creator-sdk`

### Problem: Security audit flags dependency vulnerability

**Solution:**
- Identify vulnerable dependency: `npm audit`
- Update: `npm update [package-name]`
- Re-run security scan: `npm audit`
- Resubmit to marketplace

### Problem: "Insufficient test coverage" error

**Solution:**
- Check coverage: `npm test -- --coverage`
- Target: > 80% line coverage
- Test uncovered lines: `jest --collectCoverageFrom="src/**"`
- Add tests for edge cases

---

## Next Steps

### After Your First Skill Launches:

1. **Monitor Usage**
   - Check analytics dashboard (downloads, user feedback)
   - Respond to reviews and bug reports within 48 hours

2. **Iterate**
   - Collect creator feedback
   - Release v1.1.0 with improvements
   - Track adoption curve

3. **Monetize**
   - Consider switching from "free" to "freemium" ($5/month)
   - Or add paid premium features
   - Watch earnings grow (target: €500–€5K/month for popular skills)

4. **Scale**
   - Author a second skill (pick a different problem)
   - Build skill bundles (e.g., "Governance Starter Pack")
   - Collaborate with other creators

### Creator Success Stories:

**Alice (Compliance Expert)** → Published "GDPR Compliance Auditor"
- Launched Sep 2026, free
- 500 downloads in first month
- Switched to freemium ($10/month) → €2,500/month by Q1 2027

**Bob (Data Engineer)** → Published "Settlement Anomaly Detector"
- Launched Oct 2026
- Focused on enterprise customers ($100/month)
- 20 paid subscribers → €2,000/month by Q2 2027

**Carol (Legal Expert)** → Published "Multi-Sig Approval Workflow"
- Launched Nov 2026
- Specialized in high-compliance enterprises
- €5,000/month within 2 months

---

## Support & Community

**Questions?**
- Email: creators@sovereignnexus.ai
- Discord: https://discord.gg/sovereignnexus
- Forum: https://forum.sovereignnexus.ai/creators

**Resources:**
- [Skill API Reference](https://docs.sovereignnexus.ai/skills/api)
- [GitHub Skill Templates](https://github.com/sovereignnexus/skill-templates)
- [Security Audit Checklist](https://docs.sovereignnexus.ai/skills/security-checklist)
- [Marketplace Guidelines](https://marketplace.sovereignnexus.ai/guidelines)

---

## FAQ

**Q: What if my skill has a security vulnerability?**
A: You have 48 hours to patch and release v1.1.0. Failure to patch = automatic delisting.

**Q: Can I take my skill open-source after publishing?**
A: Yes! You own your skill. Open-source it on GitHub anytime. We'll link to your repo on the marketplace listing.

**Q: What if two creators publish the same skill?**
A: Both can coexist. Users choose based on rating, price, features. Competition drives quality.

**Q: Can I raise the price after launch?**
A: Yes, but existing subscribers get locked-in rate for 1 year. New subscribers pay new price.

**Q: How do I update my skill?**
A: Release a new version (1.1.0). Existing users stay on 1.0.0 unless they explicitly upgrade.

**Q: What if a creator leaves?**
A: Their skills remain on marketplace, but they no longer receive payments. (IP stays with skill, not creator)

**Q: Can I remove my skill from marketplace?**
A: Yes, but you don't get refunds from existing subscribers. Pending payouts still paid out.

---

## Conclusion

You now have everything to author, test, and publish your first governance skill.

**Next: Pick a template and implement your skill today.**

The Creator Skills Marketplace is live on Sep 16, 2026. First 100 creators to publish skills earn **2x revenue share bonus** (98% instead of 90%) for Q4 2026.

---

**Tutorial Status:** Complete (Aug 1, 2026)  
**Estimated Time:** 30 minutes  
**Quality Bar:** 8.5/10 (beginner-friendly, practical, fully tested)

**Start here:** [Create Your First Skill](#part-3-implement-your-first-skill-10-min)
