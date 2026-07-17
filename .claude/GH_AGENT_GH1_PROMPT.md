# TASK GH1: mattpocock/skills SDK Design Pattern Research

## Objective
Research the mattpocock/skills repository and extract its agent behavior package manager design pattern. Use this to design a Creator SDK TypeScript architecture.

## Scope
- Focus: mattpocock/skills repository structure, README, core pattern files
- Output: Single markdown document with design blueprint
- Deadline: 2026-07-17 EOD
- Do NOT modify existing codebase; this is pure research

## Deliverable Path
`/Users/andriileukhin/Documents/SovereignNexus/.claude/GH1_SDK_DESIGN_BLUEPRINT.md`

## Specific Deliverable Sections Required

### 1. mattpocock/skills Pattern Summary (200 words)
- How does mattpocock/skills organize composable prompts?
- What is the .claude directory format?
- How does the package manager enable agent behavior sharing?
- Key architectural decisions and why they work

### 2. Proposed Creator SDK Directory Structure
```
Show the exact file/folder layout for:
- Top-level organization
- How composable prompts are organized
- Where TypeScript SDK code lives
- How distribution/packaging works
```

### 3. Composable Prompt Pattern Design for TypeScript SDK
- What is the pattern for "composable prompts" in mattpocock/skills?
- How would this apply to Creator SDK in TypeScript?
- Example: one composable prompt component with its structure
- How do prompts compose together?

### 4. Integration with siss-night-cycle Operators
- Review /Users/andriileukhin/Documents/SovereignNexus/crates/siss-night-cycle/src/operators/mod.rs
- How would mattpocock/skills pattern integrate with existing operators?
- Are there naming/structure changes needed?
- Show 1-2 examples of how a night-cycle operator becomes a composable prompt

### 5. File Path Examples for SDK Distribution
- Where would the SDK live in the repo?
- How would it be published (npm? GitHub? internal?)?
- Example import paths for users of the SDK
- Example: how a user would load a composable prompt

## Research Steps
1. Visit https://github.com/mattpocock/skills
2. Read README and understand high-level purpose
3. Examine directory structure and key files
4. Identify core pattern (how prompts are organized, shared, composed)
5. Look for any TypeScript-specific implementation if present
6. Document findings in the sections above

## Output Format
- Markdown file with clear section headings
- Include code blocks for directory structures and examples
- Include 1-2 screenshots or code snippets from mattpocock/skills showing the pattern
- No more than 2000 words total
- Focus on actionable design decisions for Creator SDK

## Completion Verification
- File exists at /Users/andriileukhin/Documents/SovereignNexus/.claude/GH1_SDK_DESIGN_BLUEPRINT.md
- All 5 sections completed with concrete examples
- Pattern is clear enough that another developer could implement it
- Integration with siss-night-cycle is specific and actionable

## Post-Completion
After deliverable is complete, post a comment on task #162 with:
- Link to GH1_SDK_DESIGN_BLUEPRINT.md
- One-sentence summary of the mattpocock/skills pattern
- Recommendation: proceed with Creator SDK implementation using this pattern? (Yes/No)
