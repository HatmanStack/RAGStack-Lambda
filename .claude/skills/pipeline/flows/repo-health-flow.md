# Pipeline Flow: repo-health

## Overview

```text
+----------+     +----------+     +--------------+     +------------+     +---------+     +-----------+     +---------+     +----------+
| Auditor  | --> | Planner  | --> | Plan Reviewer| --> | Hygienist  | --> | Health  | --> | Fortifier | --> | Health  | --> | Re-Audit |
|          |     |          |     |              |     | (cleanup)  |     | Review  |     | (harden)  |     | Review  |     |          |
+----------+     +----------+     +--------------+     +------------+     +---------+     +-----------+     +---------+     +----------+
                        ^                |                    ^                |                ^                |                |
                        |  REVISION_     |                   |  CHANGES_      |               |  CHANGES_      |                |
                        +--REQUIRED------+                   +--REQUESTED-----+               +--REQUESTED-----+                |
                                                                                                                                |
                                                 +--------------------------------------------------------------------------+  |
                                                 | Unverified items? Loop back to Planner                                   |  |
                                                 +--------------------------------------------------------------------------+  |
```

## Intake Document

The intake skill produces `docs/plans/$ARGUMENTS/health-audit.md` with:
- `type: repo-health` in frontmatter
- Tech debt ledger (prioritized by severity)
- Quick wins identified
- Automated scan results

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
- `.claude/skills/pipeline/health-hygienist.md`
- `.claude/skills/pipeline/health-fortifier.md`
- `.claude/skills/pipeline/health-reviewer.md`
- `.claude/skills/pipeline/health-auditor.md`

If any file is missing, **stop and report** which files are absent.

## Stage 1: Initial Audit (already done by intake)

Skip this stage — the intake skill (`/repo-health`) already ran the auditor and produced `health-audit.md`. Read it to understand the findings.

## Critical Rule: No Auditor Agents During Planning or Implementation

Auditor agents are **token-expensive**. They run exactly twice in the full lifecycle:

1. **Once during `/repo-health` intake** — produces health-audit.md
2. **Never again** — Stage 4 (Verification) uses the existing code reviewer to spot-check findings, NOT the auditor agent

**NEVER** re-run the auditor agent at any point during the pipeline. The planner, implementer, and verification reviewer work from health-audit.md and feedback.md.

## Stage 2: Planning (Planner ↔ Plan Reviewer GAN Loop)

**Max iterations: 3.**

The planner reads `health-audit.md` instead of `brainstorm.md`. The planner creates ONE unified remediation plan with phases sequenced as:
- **Early phases:** Subtractive work (cleanup, dead code, unused deps) — Hygienist executes these
- **Later phases:** Additive work (linting, CI, hooks, type strictness) — Fortifier executes these

### 2a: Spawn Planner

- **Read** `planner.md` for the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Input document: docs/plans/$ARGUMENTS/health-audit.md (this replaces brainstorm.md)

This is a REPO HEALTH remediation plan. Read the audit document — it contains a prioritized tech debt ledger with specific file:line findings across 4 vectors (Architectural, Structural, Operational, Hygiene).

Key constraints:
- SUBTRACTIVE phases FIRST (cleanup, deletion, consolidation) — tag these phases with "[HYGIENIST]" in the phase title
- ADDITIVE phases LAST (linting, CI, hooks, type safety) — tag these phases with "[FORTIFIER]" in the phase title
- The hygienist must NOT add code or abstractions — only remove and simplify
- The fortifier must NOT fix existing code — only add guardrails that enforce the clean state
- Quick wins from the audit should be in Phase 1
- CRITICAL findings before HIGH before MEDIUM

Phase sizing: cleanup and hardening phases are typically smaller than feature phases. Size to the work — a single-phase plan is fine if the scope fits. Do NOT pad phases to reach ~50k tokens.

Read the health-audit.md, explore the codebase, and create the plan files at docs/plans/$ARGUMENTS/.

When complete, end with: PLAN_COMPLETE
</task>
```

### 2b: Spawn Plan Reviewer

Standard plan review process — see main SKILL.md Stage 1b.

Loop until `PLAN_APPROVED` or max iterations.

## Stage 3: Implementation (Per-Phase GAN Loops)

**Max iterations per phase: 3.**

Process phases sequentially. The orchestrator determines which implementer role to use based on the phase title tag:

### For [HYGIENIST] phases

- **Read** `health-hygienist.md` for the role prompt
- Spawn implementer agent with hygienist role prompt
- After implementation, spawn **Health Reviewer** (`health-reviewer.md`) for review
- Loop until `PHASE_APPROVED` or max iterations

### For [FORTIFIER] phases

- **Read** `health-fortifier.md` for the role prompt
- Spawn implementer agent with fortifier role prompt
- After implementation, spawn **Health Reviewer** (`health-reviewer.md`) for review
- Loop until `PHASE_APPROVED` or max iterations

**Agent spawn format is the same as main SKILL.md Stage 2, substituting the appropriate role prompt.**

Report between phases:
```text
Phase N ([HYGIENIST|FORTIFIER]) approved after M iteration(s).
Remaining phases: [list]
```

## Stage 4: Verification

After all phases are `PHASE_APPROVED`, run a single verification agent that spot-checks the original CRITICAL and HIGH findings.

### 4a: Spawn Verification Agent

- **Read** `reviewer.md` for the role prompt
- Spawn **one Agent** with:

```xml
<role_prompt>
[Contents of reviewer.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a VERIFICATION pass after remediation. You are NOT doing a full audit — you are spot-checking that specific CRITICAL and HIGH findings were addressed.

Read docs/plans/$ARGUMENTS/health-audit.md — focus on CRITICAL and HIGH items in the Tech Debt Ledger.

For each CRITICAL/HIGH finding:
1. Read the specific file:line referenced
2. Verify the issue was addressed (Glob/Grep/Read)
3. Run tests if the finding was about test coverage or behavior

Also run the full test suite to catch regressions.

Report which findings are VERIFIED (fixed) vs UNVERIFIED (still present).
MEDIUM/LOW findings do not need verification — they are acceptable to carry.

If all CRITICAL/HIGH verified and tests pass: end with VERIFIED
If any CRITICAL/HIGH unverified or tests fail: list the unverified items, then end with UNVERIFIED
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

Verification checked [N] CRITICAL/HIGH findings from health-audit.md:
- [X] verified (fixed)
- Remaining MEDIUM/LOW: [Y] (acceptable, not gated)
Tests: [all passing]

All remediation is committed and verified.
```

### If unverified

```text
Pipeline paused for $ARGUMENTS.

Verification found [Y] unverified CRITICAL/HIGH items:
- [finding — file:line — still present because...]

Options:
A) Re-enter planning for unverified items: /pipeline $ARGUMENTS
B) Review manually and decide
C) Accept as-is
```
