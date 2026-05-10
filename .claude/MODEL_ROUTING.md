# Claude Code Model Routing — SISS Development

## Switch models with: `/model <model-name>`

## 3-Tier Strategy

| Tier | Model | Use for |
|------|-------|---------|
| **Planning** | `claude-opus-4-5` | Architecture, SISS specs, complex multi-file debugging, major refactors |
| **Mid-tier** | `claude-sonnet-4-5` | Code reviews, medium-complexity logic, partial refactors, pipeline adjustments |
| **Execution** | `claude-haiku-3-5` | Code writing, test generation, boilerplate, iteration loops, small edits |

## Workflow

1. Start session on **Opus** → generate plan, architecture, acceptance tests
2. `/model claude-haiku-3-5` → implement code, write tests, iterate (free-tier equivalent cost)
3. `/model claude-sonnet-4-5` → when Haiku output needs more reasoning but Opus is overkill
4. `/model claude-opus-4-5` → return only for major architectural decisions or deep SISS debugging

## Cost Ratio (approximate)

- Haiku : Sonnet : Opus ≈ 1 : 5 : 20
- Targeting ~70–80% of tokens at Haiku tier = ~10–15x cost reduction vs all-Opus

## SISS-Specific Guidance

- `siss-graph-core` / `siss-graph-db` schema changes → **Opus** (architectural impact)
- `siss-job-router` routing logic → **Sonnet** (medium complexity)
- `siss-agent-card` / `siss-agent-shell` impl → **Haiku** (straightforward Rust)
- `siss-behavioral-firewall` rule logic → **Sonnet** (needs reasoning, not architecture)
- Boilerplate, tests, error handling → **Haiku**
