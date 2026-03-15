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
3. **Check eval.md** for re-evaluation sections (headers like `## Re-Evaluation Cycle N`):
   - If re-evaluation results exist with all pillars ≥ 9 → pipeline complete, report and stop
   - If re-evaluation results exist with pillars < 9 → enter at Stage 2 with updated targets
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

### 2a (Re-entry): Spawn Planner After Re-Evaluation

When looping back from Stage 4 with updated scores:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Input document: docs/plans/$ARGUMENTS/eval.md

This is a RE-EVALUATION remediation plan (cycle N). The eval.md has been updated with new scores from the latest re-evaluation. Read the most recent "Re-Evaluation Cycle" section — it contains updated scores and NEW remediation targets for pillars still below 9/10.

Create a NEW remediation plan addressing ONLY the remaining targets. Previous plan files may exist — create new Phase-N.md files starting after the last existing phase number.

When complete, end with: PLAN_COMPLETE
</task>
```

### 2b: Spawn Plan Reviewer

Standard plan review process — see main SKILL.md Stage 1b.

Loop until `PLAN_APPROVED` or max iterations.

## Stage 3: Implementation (Per-Phase Implementer ↔ Reviewer GAN Loop)

**Max iterations per phase: 3.**

Standard implementation process — see main SKILL.md Stage 2 (including State Recovery for per-phase resume detection). The implementer executes the remediation plan using the existing `implementer.md` role prompt.

**Note:** The existing implementer and code reviewer roles work here without modification. The plan tells them what to do — they don't need to know it's an eval remediation vs. a feature build.

## Stage 4: Targeted Re-Evaluation

After all phases are implemented and approved, re-evaluate only the lenses that have pillars below their threshold.

### 4a: Determine Which Evaluators to Re-Run

Read the Calibration section from eval.md. Check which evaluator lenses have at least one pillar below its effective threshold (from `pillar_overrides`). Only re-run those evaluators.

- If only Hire pillars need work → spawn only the Hire evaluator
- If Hire + Day 2 need work → spawn Hire and Day 2 in parallel
- If all 3 need work → spawn all 3 in parallel

**Do NOT re-run evaluators whose pillars are all at or above their thresholds.** This saves agent context and tokens.

### 4b: Spawn Required Evaluators

**Read** the role prompt files for the evaluators being re-run. Spawn agents in parallel.

For each evaluator being re-run, use this prompt (substituting the appropriate role prompt and signal):

```xml
<role_prompt>
[Contents of eval-{hire|stress|day2}.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a RE-EVALUATION after remediation. Read the previous scores at docs/plans/$ARGUMENTS/eval.md.

Re-evaluate the codebase. Focus ONLY on the REMEDIATION TARGETS from the prior round for your pillars that were below threshold. Re-score all 4 of your pillars — scores can go up or down.

End with: EVAL_{HIRE|STRESS|DAY2}_COMPLETE
</task>
```

Wait for all spawned agents. Verify the expected `EVAL_*_COMPLETE` signals are present.

### 4c: Combine Results

The **orchestrator** (you) must:
1. Read all re-evaluation outputs
2. For evaluators that were NOT re-run, carry forward their previous scores unchanged
3. Use **Write** to append a new `## Re-Evaluation Cycle N` section to `docs/plans/$ARGUMENTS/eval.md` with:
   - Updated scorecard (before → after for each pillar, noting which were re-evaluated vs. carried forward)
   - New REMEDIATION TARGETS for any pillar still below its effective threshold
   - Full evaluator outputs for re-run lenses only
4. Check: are ALL pillars at or above their effective thresholds? (default: 9/10, or custom threshold from `pillar_overrides`, or excluded if marked `accept`)

### If all pillars meet thresholds: Report success

```text
Pipeline complete for $ARGUMENTS.

Final verdict: ALL PILLARS AT TARGET

[Final scorecard showing all 12 pillars with initial → final scores and thresholds]
[Note any pillars accepted below 9 via user override]

All remediation is committed and verified.
```

### If any pillar below threshold: Loop back to Stage 2

- Use the re-entry planner prompt (Stage 2a Re-entry) with the updated eval.md
- **Max re-evaluation cycles: 3.** If not all at threshold after 3 full cycles, stop and surface to user.

Report between cycles:
```text
Re-evaluation cycle N complete.
Pillars still below threshold: [list with scores and targets]
Evaluators re-run: [list]
Evaluators skipped (all pillars met): [list]
Re-entering planning for remaining targets...
```
