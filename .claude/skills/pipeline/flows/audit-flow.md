# Pipeline Flow: audit (Unified)

## Overview

When multiple intake docs exist, the pipeline creates ONE plan with phases tagged by implementer type. Each phase routes to the correct implementer/reviewer pair.

```text
+-----------+     +----------+     +--------------+     +-------------------+     +-------------------+     +-------------+
| All Audit | --> | Planner  | --> | Plan Reviewer| --> | Tagged Phases     | --> | Tagged Reviewers  | --> | Re-Evaluate |
| Docs      |     | (1 plan) |     |              |     | [HYGIENIST]       |     | health-reviewer   |     | + Re-Audit  |
|           |     |          |     |              |     | [FORTIFIER]       |     | health-reviewer   |     |             |
|           |     |          |     |              |     | [IMPLEMENTER]     |     | reviewer          |     |             |
|           |     |          |     |              |     | [DOC-ENGINEER]    |     | doc-reviewer      |     |             |
+-----------+     +----------+     +--------------+     +-------------------+     +-------------------+     +-------------+
                        ^                |                       ^                        |                        |
                        |  REVISION_     |                      |  CHANGES_              |                        |
                        +--REQUIRED------+                      +--REQUESTED-------------+                        |
                                                                                                                  |
                                                         +--------------------------------------------------------+
                                                         | Any gate not met? Loop back to Planner
                                                         +--------------------------------------------------------+
```

## Intake Documents

Multiple docs exist at `docs/plans/$ARGUMENTS/`:
- `health-audit.md` (if present) — tech debt findings
- `eval.md` (if present) — 12-pillar scores with remediation targets
- `doc-audit.md` (if present) — documentation drift findings

## Phase Tags and Role Routing

| Phase Tag | Implementer Role | Reviewer Role | Work Type |
|-----------|-----------------|---------------|-----------|
| `[HYGIENIST]` | `health-hygienist.md` | `health-reviewer.md` | Subtractive: delete dead code, remove unused deps, simplify |
| `[FORTIFIER]` | `health-fortifier.md` | `health-reviewer.md` | Additive: lint configs, CI, hooks, type strictness |
| `[IMPLEMENTER]` | `implementer.md` | `reviewer.md` | Code fixes: architecture, error handling, performance, testing |
| `[DOC-ENGINEER]` | `doc-engineer.md` | `doc-reviewer.md` | Doc fixes: delete stale, fix drift, add prevention |

## State Recovery (Resume Detection)

Before starting any stage, detect prior progress:

1. **Check for plan files**: Glob for `docs/plans/$ARGUMENTS/Phase-*.md`
2. **Check feedback.md** (if it exists):
   - `PLAN_APPROVED` with no phase progress → enter at Stage 2 (Implementation)
   - `PHASE_APPROVED` for all phases → enter at Stage 3 (Re-Evaluation)
   - OPEN `CODE_REVIEW` items → enter at Stage 2 at the correct phase with revision instructions
   - OPEN `PLAN_REVIEW` items → enter at Stage 1 with revision instructions
3. **Check for re-evaluation/re-audit sections** in eval.md or health-audit.md or doc-audit.md
4. **No plan files, no feedback.md** → enter at Stage 1 (first run)

Apply the same per-phase state recovery logic from the main SKILL.md (check `PHASE_APPROVED`, OPEN/resolved `CODE_REVIEW`, and git commits per phase).

Report detected state to the user before continuing.

## Pre-Flight: Role File Validation

Before spawning any agents, verify all required role prompt files exist using **Glob**:
- `.claude/skills/pipeline/planner.md`
- `.claude/skills/pipeline/plan_reviewer.md`

And based on which intake docs are present:
- If `health-audit.md`: `.claude/skills/pipeline/health-hygienist.md`, `.claude/skills/pipeline/health-fortifier.md`, `.claude/skills/pipeline/health-reviewer.md`, `.claude/skills/pipeline/health-auditor.md`
- If `eval.md`: `.claude/skills/pipeline/implementer.md`, `.claude/skills/pipeline/reviewer.md`, `.claude/skills/pipeline/eval-hire.md`, `.claude/skills/pipeline/eval-stress.md`, `.claude/skills/pipeline/eval-day2.md`
- If `doc-audit.md`: `.claude/skills/pipeline/doc-engineer.md`, `.claude/skills/pipeline/doc-reviewer.md`, `.claude/skills/pipeline/doc-auditor.md`

If any file is missing, **stop and report** which files are absent.

## Critical Rule: No Evaluator/Auditor Agents During Planning or Implementation

Evaluator and auditor agents are **token-expensive**. They run exactly twice in the full lifecycle:

1. **Once during `/audit` intake** — produces the intake docs
2. **Never again** — Stage 3 (Verification) uses the existing code reviewer to spot-check findings, NOT the evaluator/auditor agents

**NEVER** re-run evaluator or auditor agents at any point during the pipeline. The planner, implementer, and verification reviewer work from the intake docs and feedback.md.

## Stage 1: Planning (Planner ↔ Plan Reviewer GAN Loop)

**Max iterations: 3.**

The planner reads ALL intake docs and creates ONE unified plan.

### 1a: Spawn Planner

- **Read** `planner.md` for the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a UNIFIED AUDIT remediation plan. Multiple intake documents exist — read ALL of them:
- docs/plans/$ARGUMENTS/health-audit.md (if exists) — tech debt findings
- docs/plans/$ARGUMENTS/eval.md (if exists) — 12-pillar evaluation scores
- docs/plans/$ARGUMENTS/doc-audit.md (if exists) — documentation drift findings

Create ONE plan with phases sequenced in this order:
1. [HYGIENIST] phases FIRST — subtractive cleanup (dead code, unused deps, simplify)
2. [IMPLEMENTER] phases NEXT — code fixes (architecture, error handling, performance, testing)
3. [FORTIFIER] phases NEXT — additive guardrails (lint, CI, hooks, type safety)
4. [DOC-ENGINEER] phases LAST — documentation fixes and prevention tooling

Key constraints:
- Tag EVERY phase title with exactly one of: [HYGIENIST], [IMPLEMENTER], [FORTIFIER], [DOC-ENGINEER]
- The tag determines which implementer and reviewer handle that phase
- Cleanup before structural fixes before guardrails before docs
- Where findings overlap across audit types, consolidate into a single task
- Quick wins and CRITICAL findings should be in early phases
- Phase sizing: remediation phases are typically smaller than feature phases. Size to the work — a single-phase plan is fine if the scope fits. Do NOT pad phases to reach ~50k tokens.

Explore the codebase and create the plan files at docs/plans/$ARGUMENTS/.

When complete, end with: PLAN_COMPLETE
</task>
```

### 1a (Re-entry): Spawn Planner After Re-Evaluation

When looping back from Stage 3 with updated scores/findings:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a RE-EVALUATION remediation plan (cycle N). The intake docs have been updated with new scores/findings from the latest re-evaluation. Read the most recent sections in each intake doc for updated remediation targets.

Create a NEW remediation plan addressing ONLY the remaining targets. Previous plan files may exist — create new Phase-N.md files starting after the last existing phase number.

Tag every phase with [HYGIENIST], [IMPLEMENTER], [FORTIFIER], or [DOC-ENGINEER].

When complete, end with: PLAN_COMPLETE
</task>
```

### 1b: Spawn Plan Reviewer

Standard plan review process — see main SKILL.md Stage 1b.

Loop until `PLAN_APPROVED` or max iterations.

## Stage 2: Implementation (Per-Phase GAN Loops)

**Max iterations per phase: 3.**

Identify all phases by Glob for `docs/plans/$ARGUMENTS/Phase-*.md` (excluding Phase-0). Process sequentially.

### Phase Tag Routing

For each phase, read the phase title to determine the tag, then spawn the correct implementer and reviewer:

**[HYGIENIST] phases:**
- Implementer: **Read** `health-hygienist.md`, spawn with hygienist role prompt
- Reviewer: **Read** `health-reviewer.md`, spawn with health reviewer role prompt

**[FORTIFIER] phases:**
- Implementer: **Read** `health-fortifier.md`, spawn with fortifier role prompt
- Reviewer: **Read** `health-reviewer.md`, spawn with health reviewer role prompt

**[IMPLEMENTER] phases:**
- Implementer: **Read** `implementer.md`, spawn with standard implementer role prompt
- Reviewer: **Read** `reviewer.md`, spawn with standard code reviewer role prompt

**[DOC-ENGINEER] phases:**
- Implementer: **Read** `doc-engineer.md`, spawn with doc engineer role prompt
- Reviewer: **Read** `doc-reviewer.md`, spawn with doc reviewer role prompt

Agent spawn format is the same as main SKILL.md Stage 2, substituting the appropriate role prompt per phase tag.

Loop until `PHASE_APPROVED` or max iterations per phase.

Report between phases:
```text
Phase N [TAG] approved after M iteration(s).
Remaining phases: [list with tags]
```

## Stage 3: Verification

After all phases are `PHASE_APPROVED`, run a single verification agent that spot-checks the original findings from all intake docs. This is NOT a full re-evaluation — it's a targeted check using the existing code reviewer role.

### 3a: Spawn Verification Agent

- **Read** `reviewer.md` for the role prompt
- Spawn **one Agent** with:

```xml
<role_prompt>
[Contents of reviewer.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a VERIFICATION pass after remediation. You are NOT doing a full code review — you are spot-checking that specific findings from the original audit were addressed.

Read the original intake docs to get the list of findings:
- docs/plans/$ARGUMENTS/eval.md (if exists) — check REMEDIATION TARGETS
- docs/plans/$ARGUMENTS/health-audit.md (if exists) — check CRITICAL and HIGH findings
- docs/plans/$ARGUMENTS/doc-audit.md (if exists) — check DRIFT, STALE, and BROKEN LINK findings

For each finding:
1. Read the specific file:line referenced in the finding
2. Verify the issue was addressed (Glob/Grep/Read)
3. Run tests if the finding was about test coverage or behavior

Report which findings are VERIFIED (fixed) vs UNVERIFIED (still present).

Also run the full test suite to catch regressions.

If all findings verified and tests pass: end with VERIFIED
If any findings unverified or tests fail: list the unverified items, then end with UNVERIFIED
</task>
```

### 3b: Assess Results

- If `VERIFIED` → report success
- If `UNVERIFIED` → the orchestrator reads the unverified items and decides:
  - If minor (< 3 items): report to user with specific items, let them decide
  - If significant: loop back to Stage 1 with the unverified items as new targets

**Max verification cycles: 2.** If items remain unverified after 2 cycles, stop and surface to user.

### If verified: Report success

```text
Pipeline complete for $ARGUMENTS.

Final verdict: VERIFIED

Verification checked [N] findings from original audit:
- [X] verified (fixed)
- [Y] unverified (if any, listed below)

Tests: [all passing / N failures]

All remediation is committed and verified.
```

### If unverified: Report to user

```text
Pipeline paused for $ARGUMENTS.

Verification found [Y] unverified items:
- [finding 1 — file:line — still present because...]
- [finding 2 — ...]

Options:
A) Re-enter planning for unverified items: /pipeline $ARGUMENTS
B) Review manually and decide
C) Accept as-is
```
