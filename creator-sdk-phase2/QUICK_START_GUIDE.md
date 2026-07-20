# Creator SDK Phase 2: Quick Start Guide
## Author Your First Skill in 30 Minutes

**TL;DR:** Copy template → Write 50 lines of code → Test → Publish → Earn 90% revenue

---

## The 30-Minute Path

### Minute 0–5: Setup
```bash
npm install -g @sovereignnexus/cli
mkdir my-first-skill && cd my-first-skill
npm init -y
npm install --save-dev typescript jest @sovereignnexus/creator-sdk
mkdir src tests
```

### Minute 5–10: Write Metadata
Create `SKILL.json`:
```json
{
  "id": "my-first-skill",
  "name": "My First Skill",
  "version": "1.0.0",
  "author": { "type": "Creator", "name": "You" },
  "governance": { "modifiable": true, "auditable": true },
  "pricing": { "model": "free" }
}
```

### Minute 10–20: Write Code
Create `src/index.ts`:
```typescript
export const myFirstSkill = {
  id: 'my-first-skill',
  execute: async (context, input) => {
    // Your logic here (20 lines)
    return { result: "success" };
  }
};
```

### Minute 20–25: Write Tests
Create `tests/index.test.ts`:
```typescript
it('should work', async () => {
  const result = await myFirstSkill.execute({}, {});
  expect(result.result).toBe('success');
});
```

Run:
```bash
npm test
```

### Minute 25–30: Publish
```bash
sns-cli skill publish . --category settlement-verification
```

**Done.** Your skill is live on the marketplace.

---

## 5 Skill Ideas (Pick One)

1. **Settlement Auditor** (20 min) → Verify 99/1 split
2. **Anomaly Detector** (25 min) → Flag unusual settlements
3. **Rate Limiter** (20 min) → Enforce token budgets
4. **GDPR Erasure** (30 min) → Handle data deletion
5. **Approval Workflow** (25 min) → Require multi-party sign-off

---

## Skill Template (Copy & Adapt)

```typescript
// src/index.ts
import { SkillDefinition } from '@sovereignnexus/creator-sdk';

export const mySkill: SkillDefinition = {
  id: 'my-skill',
  name: 'My Skill',
  author: { type: 'Creator', name: 'You' },
  version: '1.0.0',

  execute: async (context, input) => {
    try {
      // Step 1: Fetch data
      const data = await context.api.fetch(input.id);

      // Step 2: Process
      const result = processData(data);

      // Step 3: Return
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }
};

function processData(data) {
  // Your logic here
  return data;
}
```

---

## Test Template

```typescript
// tests/index.test.ts
import { mySkill } from '../src/index';

describe('My Skill', () => {
  it('should process data', async () => {
    const context = { api: { fetch: jest.fn() } };
    context.api.fetch.mockResolvedValue({ value: 100 });

    const result = await mySkill.execute(context, { id: 'test' });

    expect(result.success).toBe(true);
  });

  it('should handle errors', async () => {
    const context = { api: { fetch: jest.fn() } };
    context.api.fetch.mockRejectedValue(new Error('Network error'));

    const result = await mySkill.execute(context, { id: 'test' });

    expect(result.success).toBe(false);
  });
});
```

---

## Publishing Checklist

- [ ] SKILL.json created + valid
- [ ] src/index.ts written (50–200 LOC)
- [ ] tests/index.test.ts written (3+ tests)
- [ ] `npm test` passes
- [ ] README.md written (200+ words)
- [ ] safety-checklist.md completed

**Then:**
```bash
sns-cli skill publish . --category YOUR_CATEGORY --pricing-model free
```

---

## Skill Categories

Pick one:
- `settlement-verification` — Verify 99/1 splits
- `compliance` — GDPR, SOX, HIPAA
- `rate-limiting` — Token budgets
- `approval-workflow` — Multi-party auth
- `analytics` — Revenue insights
- `custom-governance` — Rule engines

---

## Revenue Potential

| Skill Type | Downloads/Month | Pricing | Monthly Revenue |
|------------|-----------------|---------|-----------------|
| Popular (Settlement) | 100+ | Free | €0 (build audience) |
| Popular + Freemium | 100+ | €5/mo | €450 (90% = €405) |
| Enterprise (Compliance) | 20+ | €50/mo | €900 (90% = €810) |
| Niche (Multi-Sig) | 10+ | €100/mo | €900 (90% = €810) |

---

## Getting Help

- **Email:** creators@sovereignnexus.ai
- **Discord:** https://discord.gg/sovereignnexus
- **Docs:** https://docs.sovereignnexus.ai/skills
- **GitHub:** https://github.com/sovereignnexus/skill-templates

---

## FAQ

**Q: How long to earn first €100?**
A: 1–3 months (depends on skill quality and category popularity)

**Q: What if my skill has a bug?**
A: Release v1.1.0 with fix. Existing users stay on 1.0.0.

**Q: Can I charge money?**
A: Yes. Switch to "freemium" ($5–$100/month) after proving adoption.

**Q: What if my skill gets bad reviews?**
A: Respond to feedback, improve, release new version. Show you care.

**Q: Can I delete my skill?**
A: Yes, but pending payouts still sent. Earnings freeze.

---

**Start Now:** [Full Onboarding Guide](SDK_PHASE2_CREATOR_ONBOARDING.md)

**Questions?** Email creators@sovereignnexus.ai
