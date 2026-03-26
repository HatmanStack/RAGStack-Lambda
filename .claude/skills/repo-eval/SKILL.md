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

Ask scoping questions **one at a time**, preferring multiple choice. Wait for each answer before asking the next.

The code evaluation runs 3 evaluator agents in parallel, each scoring 4 pillars (12 total). These questions calibrate the evaluation.

**Question 1** — Known pain points give the evaluators a starting hypothesis instead of scanning cold:

```text
Are there parts of the codebase you already know are problematic?
Things that keep breaking, areas you dread touching, modules that slow down every PR.

A) Yes (tell me which areas and what's wrong)
B) No — scan everything with fresh eyes
```

**Question 2** — Role level sets the scoring bar:

```text
What role level should I evaluate this codebase against?

A) Junior Developer — fundamentals: readability, basic error handling, test presence
B) Mid-Level Developer — patterns: separation of concerns, consistent conventions, test coverage
C) Senior Developer — production: defensive coding, observability, performance awareness, type rigor
D) Staff+ / Principal — systems: architectural coherence, scalability, operational excellence
```

**Question 3** — Focus areas weight what evaluators pay extra attention to (they still score all 12 pillars):

```text
Any specific concerns the evaluators should weight more heavily?

A) Performance — hot paths, algorithmic complexity, resource management
B) Security — input validation, auth patterns, secrets handling
C) Testing — coverage quality, test architecture, edge cases
D) Architecture — separation of concerns, modularity, coupling
E) Multiple (tell me which)
F) None — balanced evaluation across all pillars
```

**Question 4** — Scope and exclusions:

```text
What should the evaluators look at?

A) Full repo, standard exclusions (vendor, generated, node_modules, __pycache__)
B) Full repo, no exclusions
C) Specific directories only (tell me which to include or exclude)
```

**Question 5** — Pillar overrides. By default, `/pipeline` remediates until all 12 pillars hit 9/10. Some pillars may not be improvable through code changes. The 12 pillars are:
- **Hire lens:** Problem-Solution Fit, Architecture, Code Quality, Creativity
- **Stress lens:** Pragmatism, Defensiveness, Performance, Type Rigor
- **Day 2 lens:** Test Value, Reproducibility, Git Hygiene, Onboarding

```text
Any pillars to accept below the default 9/10 threshold?

A) None — require 9/10 on all 12 pillars
B) Specific overrides (tell me which pillars and target scores, e.g., "Creativity: 7, Git Hygiene: accept")
```

Record overrides in the eval.md frontmatter.

### Step 2: Generate Plan Identifier

Generate the directory name: `YYYY-MM-DD-eval-slug`
- Date: today's date
- Slug: short name for the repo being evaluated (e.g., `eval-ragstack`, `eval-billing-api`)
- Location: `docs/plans/YYYY-MM-DD-eval-slug/`

Create the directory.

### Step 3: Run 3 Evaluators (Parallel)

**You** (the orchestrator) must read the role prompt files and embed their contents in each agent's prompt. Agents cannot access skill directory files.

1. **Read** `skills/pipeline/eval-hire.md` — store contents as `HIRE_PROMPT`
2. **Read** `skills/pipeline/eval-stress.md` — store contents as `STRESS_PROMPT`
3. **Read** `skills/pipeline/eval-day2.md` — store contents as `DAY2_PROMPT`

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

### Step 4: Validate and Combine Results

Verify each evaluator's output contains its completion signal before proceeding:
- Evaluator 1: check for `EVAL_HIRE_COMPLETE`
- Evaluator 2: check for `EVAL_STRESS_COMPLETE`
- Evaluator 3: check for `EVAL_DAY2_COMPLETE`

If any signal is missing, the agent may have been truncated. Report the incomplete evaluator to the user and do NOT write eval.md with partial data.

If all signals present, **Write** `docs/plans/YYYY-MM-DD-eval-slug/eval.md`:

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

### Step 5: Log to Manifest

Append an entry to `.claude/skill-runs.json` in the repo root. If the file does not exist, create it with an empty array first.

```json
{
  "skill": "repo-eval",
  "date": "YYYY-MM-DD",
  "plan": "YYYY-MM-DD-eval-slug"
}
```

- Read the existing file, parse the JSON array, append the new entry, and write it back
- If the file is malformed, overwrite it with a fresh array containing only the new entry

### Step 6: Handoff

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
- **DO NOT** re-run evaluator agents after writing eval.md — they run exactly once here. Re-evaluation happens in `/pipeline` after all remediation is complete.
- **DO NOT** start remediation — your only output is the eval doc
- **DO** include full evaluator outputs in eval.md (the planner needs the detail)
- **DO** consolidate overlapping findings across evaluators
