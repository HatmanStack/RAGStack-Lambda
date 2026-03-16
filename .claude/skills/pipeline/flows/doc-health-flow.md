# Pipeline Flow: doc-health

## Overview

```text
+-----------+     +----------+     +--------------+     +-----------+     +----------+     +------------+
| Doc       | --> | Planner  | --> | Plan Reviewer| --> | Doc       | --> | Doc      | --> | Re-Audit   |
| Auditor   |     |          |     |              |     | Engineer  |     | Reviewer |     |            |
+-----------+     +----------+     +--------------+     +-----------+     +----------+     +------------+
                        ^                |                    ^                |                  |
                        |  REVISION_     |                   |  CHANGES_      |                  |
                        +--REQUIRED------+                   +--REQUESTED-----+                  |
                                                                                                 |
                                                 +-----------------------------------------------+
                                                 | Drift remains? Loop back to Planner
                                                 +-----------------------------------------------+
```

## Intake Document

The intake skill produces `docs/plans/$ARGUMENTS/doc-audit.md` with:
- `type: doc-health` in frontmatter
- Drift findings (doc exists, doesn't match code)
- Gap findings (code exists, no doc)
- Stale findings (doc exists, code doesn't)
- Broken links, stale code examples, config drift

## State Recovery (Resume Detection)

Before starting any stage, detect prior progress:

1. **Check for plan files**: Glob for `docs/plans/$ARGUMENTS/Phase-*.md`
2. **Check feedback.md** (if it exists):
   - `PLAN_APPROVED` with no phase progress → enter at Stage 3 (Implementation)
   - `PHASE_APPROVED` for all phases → enter at Stage 4 (Re-Audit)
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
- `.claude/skills/pipeline/doc-engineer.md`
- `.claude/skills/pipeline/doc-reviewer.md`
- `.claude/skills/pipeline/doc-auditor.md`

If any file is missing, **stop and report** which files are absent.

## Stage 1: Initial Audit (already done by intake)

Skip this stage — the intake skill (`/doc-health`) already ran the doc auditor and produced `doc-audit.md`. Read it to understand the findings.

## Critical Rule: No Auditor Agents During Planning or Implementation

Auditor agents are **token-expensive**. They run exactly twice in the full lifecycle:

1. **Once during `/doc-health` intake** — produces doc-audit.md
2. **Never again** — Stage 4 (Verification) uses the existing code reviewer to spot-check findings, NOT the doc auditor agent

**NEVER** re-run the doc auditor agent at any point during the pipeline. The planner, doc engineer, and verification reviewer work from doc-audit.md and feedback.md.

## Stage 2: Planning (Planner ↔ Plan Reviewer GAN Loop)

**Max iterations: 3.**

The planner reads `doc-audit.md` instead of `brainstorm.md`. The planner creates ONE remediation plan with phases sequenced as:
- **Early phases:** Content fixes (delete stale, fix drifted, create stubs, fix links)
- **Later phases:** Prevention tooling (doc linting, link checking, auto-gen, CI)

### 2a: Spawn Planner

- **Read** `planner.md` for the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Input document: docs/plans/$ARGUMENTS/doc-audit.md (this replaces brainstorm.md)

This is a DOCUMENTATION HEALTH remediation plan. Read the audit document — it contains drift, gaps, stale docs, broken links, stale code examples, and config drift findings.

Key constraints:
- CONTENT FIX phases FIRST (delete stale docs, fix drift, create stubs, fix links/examples)
- PREVENTION phases LAST (doc linting, link checking, auto-gen API docs, CI integration)
- Deletions before updates before creations
- Every doc fix must be verified against actual source code — docs describe what code DOES, not what it should do
- Prevention tooling scope was defined during intake — only add what the user selected

Phase sizing: doc fix phases are typically smaller than feature phases. Size to the work — a single-phase plan is fine if the scope fits. Do NOT pad phases to reach ~50k tokens.

Read the doc-audit.md, explore the codebase, and create the plan files at docs/plans/$ARGUMENTS/.

When complete, end with: PLAN_COMPLETE
</task>
```

### 2b: Spawn Plan Reviewer

Standard plan review process — see main SKILL.md Stage 1b.

Loop until `PLAN_APPROVED` or max iterations.

## Stage 3: Implementation (Per-Phase Doc Engineer ↔ Doc Reviewer GAN Loop)

**Max iterations per phase: 3.**

- **Read** `doc-engineer.md` for the implementer role prompt
- **Read** `doc-reviewer.md` for the reviewer role prompt

Process phases sequentially. Agent spawn format matches main SKILL.md Stage 2, substituting the doc-engineer and doc-reviewer role prompts.

Report between phases:
```text
Phase N approved after M iteration(s).
Remaining phases: [list]
```

## Stage 4: Verification

After all phases are `PHASE_APPROVED`, run a single verification agent that spot-checks the original DRIFT, STALE, and BROKEN LINK findings.

### 4a: Spawn Verification Agent

- **Read** `reviewer.md` for the role prompt
- Spawn **one Agent** with:

```xml
<role_prompt>
[Contents of reviewer.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a VERIFICATION pass after remediation. You are NOT doing a full doc audit — you are spot-checking that specific findings were addressed.

Read docs/plans/$ARGUMENTS/doc-audit.md — focus on DRIFT, STALE, and BROKEN LINK findings.

For each finding:
1. Check the specific doc path and code path referenced
2. Verify drift was fixed (doc now matches code)
3. Verify stale docs were deleted or updated
4. Verify broken links now resolve (Glob for targets)

Report which findings are VERIFIED (fixed) vs UNVERIFIED (still present).
GAP findings (missing docs) do not need verification unless the plan included creating them.

If all DRIFT/STALE/BROKEN findings verified: end with VERIFIED
If any unverified: list the unverified items, then end with UNVERIFIED
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

Verification checked [N] findings from doc-audit.md:
- [X] verified (fixed)
- Remaining gaps: [Y] (not gated)

All fixes are committed and verified.
```

### If unverified

```text
Pipeline paused for $ARGUMENTS.

Verification found [Y] unverified items:
- [finding — doc path — still present because...]

Options:
A) Re-enter planning for unverified items: /pipeline $ARGUMENTS
B) Review manually and decide
C) Accept as-is
```
