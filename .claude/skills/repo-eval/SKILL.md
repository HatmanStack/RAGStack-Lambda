---
name: repo-eval
description: Evaluate a codebase across 12 pillars (hire, stress, day 2) using 3 parallel evaluator agents, then produce an eval doc for /pipeline remediation.
allowed-tools: Agent, Read, Write, Glob, Grep, Bash
---

# Repo Evaluation

You coordinate a 3-evaluator hiring panel assessment of a codebase. Each evaluator runs as a separate agent with its own context window.

## Input

`$ARGUMENTS` is optional context — the repo path, role level being evaluated, or specific concerns. If empty, evaluate the current working directory.

## Process

### Step 1: Scope the Evaluation

Ask the user 3-5 scoping questions, **one at a time**, preferring multiple choice:

```text
What role level should I evaluate this codebase against?

A) Junior Developer
B) Mid-Level Developer
C) Senior Developer
D) Staff+ / Principal
```

**Question priority:**
1. **Role level** — calibrates scoring expectations
2. **Focus areas** — any specific concerns? (performance, security, testing, etc.)
3. **Context** — is this a side project, production app, interview take-home?
4. **Exclusions** — any directories/files to skip? (vendor, generated, etc.)
5. **Pillar overrides** — any pillars to accept below 9? (e.g., "Creativity is fine at 7 — it's a CRUD app")

For pillar overrides, present the 12 pillars and ask which (if any) should have a lower threshold or be excluded from the remediation gate. Some pillars (like Creativity & Ingenuity) may not be improvable through code changes alone. Record overrides in the eval.md frontmatter.

### Step 2: Generate Plan Identifier

Generate the directory name: `YYYY-MM-DD-eval-slug`
- Date: today's date
- Slug: short name for the repo being evaluated (e.g., `eval-ragstack`, `eval-billing-api`)
- Location: `docs/plans/YYYY-MM-DD-eval-slug/`

Create the directory.

### Step 3: Run 3 Evaluators (Parallel)

**You** (the orchestrator) must read the role prompt files and embed their contents in each agent's prompt. Agents cannot access skill directory files.

1. **Read** `.claude/skills/pipeline/eval-hire.md` — store contents as `HIRE_PROMPT`
2. **Read** `.claude/skills/pipeline/eval-stress.md` — store contents as `STRESS_PROMPT`
3. **Read** `.claude/skills/pipeline/eval-day2.md` — store contents as `DAY2_PROMPT`

Then spawn **3 Agents in parallel**:

#### Evaluator 1: The Pragmatist
```xml
<role_prompt>
[Contents of eval-hire.md]
</role_prompt>

<task>
Evaluate the codebase in the current working directory.
Role level: [from Step 1]
Focus areas: [from Step 1]
Exclusions: [from Step 1]
</task>
```

#### Evaluator 2: The Oncall Engineer
```xml
<role_prompt>
[Contents of eval-stress.md]
</role_prompt>

<task>
Evaluate the codebase in the current working directory.
Role level: [from Step 1]
Focus areas: [from Step 1]
Exclusions: [from Step 1]
</task>
```

#### Evaluator 3: The Team Lead
```xml
<role_prompt>
[Contents of eval-day2.md]
</role_prompt>

<task>
Evaluate the codebase in the current working directory.
Role level: [from Step 1]
Focus areas: [from Step 1]
Exclusions: [from Step 1]
</task>
```

### Step 4: Combine Results

Read all 3 evaluator outputs. **Write** `docs/plans/YYYY-MM-DD-eval-slug/eval.md`:

```markdown
---
type: repo-eval
target: 9
role_level: [from Step 1]
date: YYYY-MM-DD
pillar_overrides:
  # Pillars with custom thresholds (omit for default 9)
  # creativity: 7
  # git_hygiene: accept
---

# Repo Evaluation: [repo name]

## Configuration
- **Role Level:** [Junior | Mid | Senior | Staff+]
- **Focus Areas:** [list]
- **Exclusions:** [list]

## Combined Scorecard

| # | Lens | Pillar | Score | Target | Status |
|---|------|--------|-------|--------|--------|
| 1 | Hire | Problem-Solution Fit | X/10 | 9 | [PASS ≥target | NEEDS WORK <target] |
| 2 | Hire | Architecture | X/10 | ... |
| 3 | Hire | Code Quality | X/10 | ... |
| 4 | Hire | Creativity | X/10 | ... |
| 5 | Stress | Pragmatism | X/10 | ... |
| 6 | Stress | Defensiveness | X/10 | ... |
| 7 | Stress | Performance | X/10 | ... |
| 8 | Stress | Type Rigor | X/10 | ... |
| 9 | Day 2 | Test Value | X/10 | ... |
| 10 | Day 2 | Reproducibility | X/10 | ... |
| 11 | Day 2 | Git Hygiene | X/10 | ... |
| 12 | Day 2 | Onboarding | X/10 | ... |

**Pillars at target (≥9):** N/12
**Pillars needing work (<9):** M/12

## Hire Evaluation — The Pragmatist
[Full evaluator output]

## Stress Evaluation — The Oncall Engineer
[Full evaluator output]

## Day 2 Evaluation — The Team Lead
[Full evaluator output]

## Consolidated Remediation Targets
[Merged and deduplicated targets from all 3 evaluators, prioritized by:
1. Lowest score first
2. Highest complexity last
3. Overlapping findings consolidated]
```

### Step 5: Handoff

```text
Evaluation complete: docs/plans/YYYY-MM-DD-eval-slug/eval.md

Scores: [N]/12 pillars at target (≥9)
Lowest: [pillar] at [X]/10

To remediate and bring all pillars to 9/10, run:
/pipeline YYYY-MM-DD-eval-slug
```

## Rules

- **DO NOT** skip the scoping questions
- **DO NOT** run evaluators sequentially — they MUST run in parallel
- **DO NOT** start remediation — your only output is the eval doc
- **DO** include full evaluator outputs in eval.md (the planner needs the detail)
- **DO** consolidate overlapping findings across evaluators
