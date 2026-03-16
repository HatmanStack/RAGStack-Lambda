# Pipeline Flow: repo-eval

## Overview

```text
+------------------+     +----------+     +--------------+     +-------------+     +----------+     +---------------+
| 3 Evaluators     | --> | Planner  | --> | Plan Reviewer| --> | Implementer | --> | Reviewer | --> | Re-Evaluate   |
| (parallel)       |     |          |     |              |     |             |     |          |     | (3 parallel)  |
+------------------+     +----------+     +--------------+     +-------------+     +----------+     +---------------+
                                ^                |                    ^                   |                |
                                |  REVISION_     |                   |  CHANGES_         |                |
                                +--REQUIRED------+                   +--REQUESTED--------+                |
                                                                                                         |
                                                 +-------------------------------------------------------+
                                                 | Any pillar < 9? Loop back to Planner with new targets
                                                 +-------------------------------------------------------+
```

## Intake Document

The intake skill produces `docs/plans/$ARGUMENTS/eval.md` with:
- `type: repo-eval` in frontmatter
- Combined output from all 3 evaluators
- 12 pillar scores (4 per evaluator)
- Remediation targets for all pillars < 9

**Write ownership:** Only the **orchestrator** writes to `eval.md`. Evaluator agents produce their output as agent responses — the orchestrator reads those responses and writes/appends to eval.md. Evaluator agents never write to eval.md directly. This prevents concurrent write conflicts when evaluators run in parallel.

## State Recovery (Resume Detection)

Before starting any stage, detect prior progress:

1. **Check for plan files**: Glob for `docs/plans/$ARGUMENTS/Phase-*.md`
2. **Check feedback.md** (if it exists):
   - `PLAN_APPROVED` with no phase progress → enter at Stage 3 (Implementation)
   - `PHASE_APPROVED` for all phases → enter at Stage 4 (Re-Evaluation)
   - OPEN `CODE_REVIEW` items → enter at Stage 3 at the correct phase with revision instructions
   - OPEN `PLAN_REVIEW` items → enter at Stage 2 with revision instructions
3. **Check feedback.md** for `VERIFIED` signal → pipeline complete, report and stop
4. **No plan files, no feedback.md** → enter at Stage 2 (first run)

Apply the same per-phase state recovery logic from the main SKILL.md (check `PHASE_APPROVED`, OPEN/resolved `CODE_REVIEW`, and git commits per phase).

Report detected state to the user before continuing.

## Pre-Flight: Role File Validation

Before spawning any agents, verify all required role prompt files exist using **Glob**:
- `.claude/skills/pipeline/planner.md`
- `.claude/skills/pipeline/plan_reviewer.md`
- `.claude/skills/pipeline/implementer.md`
- `.claude/skills/pipeline/reviewer.md`
- `.claude/skills/pipeline/eval-hire.md`
- `.claude/skills/pipeline/eval-stress.md`
- `.claude/skills/pipeline/eval-day2.md`

If any file is missing, **stop and report** which files are absent. Do not attempt to spawn agents with missing role prompts.

## Stage 1: Calibration

Read `docs/plans/$ARGUMENTS/eval.md` to understand the starting scores.

### Cross-Evaluator Calibration

The 3 evaluators score independently on different scales. Before feeding scores to the planner, the **orchestrator** must normalize:

1. Read all 3 evaluator scorecards from eval.md
2. For pillars that overlap conceptually (Architecture ↔ Defensiveness, Code Quality ↔ Performance), compare scores:
   - If scores diverge by ≥ 3 points for overlapping concerns, note the disagreement — this is signal, not noise
   - The planner should prioritize the LOWER score for overlapping areas (conservative approach)
3. Read the `pillar_overrides` from eval.md frontmatter to determine per-pillar thresholds
   - **Default threshold: 9/10** — any pillar without an explicit override must reach 9 to pass
   - The `target: 9` field in eval.md frontmatter sets this default; if missing, assume 9
   - Overridden pillars use their custom threshold (e.g., `creativity: 7`)
   - Pillars marked `accept` are excluded from the remediation gate entirely
4. Write a calibration summary to eval.md before planning begins:

```markdown
## Calibration

### Cross-Evaluator Divergences
- [Pillar A] (Hire) vs [Pillar B] (Stress): X/10 vs Y/10 — [note on what this signals]

### Effective Thresholds
| Pillar | Target | Source |
|--------|--------|--------|
| Problem-Solution Fit | 9 | default |
| Creativity | 7 | user override |
| Git Hygiene | accept | user override (excluded from gate) |
| ... | ... | ... |

### Pillars Requiring Remediation
[List only pillars below their effective threshold]
```

## Critical Rule: No Evaluator Agents During Planning or Implementation

Evaluator agents are **token-expensive**. They run exactly twice in the full lifecycle:

1. **Once during `/repo-eval` intake** — produces eval.md
2. **Never again** — Stage 4 (Verification) uses the existing code reviewer to spot-check findings, NOT the evaluator agents

**NEVER** re-run evaluator agents at any point during the pipeline. The planner, implementer, and verification reviewer work from eval.md and feedback.md.

## Stage 2: Planning (Planner ↔ Plan Reviewer GAN Loop)

**Max iterations: 3.**

The planner reads `eval.md` instead of `brainstorm.md`. The planner creates ONE unified remediation plan addressing all pillars scoring < 9 across all 3 lenses.

### 2a: Spawn Planner (Initial)

- **Read** `planner.md` for the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Input document: docs/plans/$ARGUMENTS/eval.md (this replaces brainstorm.md)

This is a REPO EVALUATION remediation plan. Read the eval document — it contains scores from 3 evaluators (Hire, Stress, Day 2) across 12 pillars. Your job is to create a remediation plan that brings ALL pillars to 9/10 or higher.

Key constraints:
- The plan addresses code quality, not features — you're improving existing code
- Prioritize by: lowest scores first, then highest complexity
- Where evaluator pillars overlap (e.g., Architecture from Hire + Defensiveness from Stress both flag the same code), consolidate into a single task
- Hygiene work (cleanup, dead code) should come in early phases
- Structural work (architecture, patterns) should come in later phases
- Fortification work (linting, CI, hooks) should come last

Phase sizing: remediation phases are typically smaller than feature phases. Size to the work — a single-phase plan is fine if the scope fits. Do NOT pad phases to reach ~50k tokens.

Read the eval.md, explore the codebase, and create the plan files at docs/plans/$ARGUMENTS/.

When complete, end with: PLAN_COMPLETE
</task>
```

### 2b: Spawn Plan Reviewer

Standard plan review process — see main SKILL.md Stage 1b.

Loop until `PLAN_APPROVED` or max iterations.

## Stage 3: Implementation (Per-Phase Implementer ↔ Reviewer GAN Loop)

**Max iterations per phase: 3.**

Standard implementation process — see main SKILL.md Stage 2 (including State Recovery for per-phase resume detection). The implementer executes the remediation plan using the existing `implementer.md` role prompt.

## Stage 4: Verification

After all phases are `PHASE_APPROVED`, run a single verification agent that spot-checks the original eval findings.

### 4a: Spawn Verification Agent

- **Read** `reviewer.md` for the role prompt
- Spawn **one Agent** with:

```xml
<role_prompt>
[Contents of reviewer.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a VERIFICATION pass after remediation. You are NOT doing a full evaluation — you are spot-checking that specific remediation targets were addressed.

Read docs/plans/$ARGUMENTS/eval.md — focus on the REMEDIATION TARGETS section.

For each target:
1. Read the specific file:line referenced
2. Verify the issue was addressed (Glob/Grep/Read)
3. Run tests if the target was about test coverage or behavior

Also run the full test suite to catch regressions.

Report which targets are VERIFIED (fixed) vs UNVERIFIED (still present).

If all targets verified and tests pass: end with VERIFIED
If any targets unverified or tests fail: list the unverified items, then end with UNVERIFIED
</task>
```

### 4b: Assess Results

- If `VERIFIED` → report success
- If `UNVERIFIED` → report unverified items to user, let them decide

**Max verification cycles: 2.** If items remain unverified after 2 cycles, stop and surface to user.

### If verified

```text
Pipeline complete for $ARGUMENTS.

Final verdict: VERIFIED

Verification checked [N] remediation targets from eval.md:
- [X] verified (fixed)
Tests: [all passing]

All remediation is committed and verified.
```

### If unverified

```text
Pipeline paused for $ARGUMENTS.

Verification found [Y] unverified items:
- [target — file:line — still present because...]

Options:
A) Re-enter planning for unverified items: /pipeline $ARGUMENTS
B) Review manually and decide
C) Accept as-is
```
