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
3. **Check doc-audit.md** for re-audit sections (headers like `## Re-Audit Cycle N`):
   - If re-audit exists with all findings resolved → pipeline complete, report and stop
   - If re-audit exists with remaining findings → enter at Stage 2 with updated targets
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

## Stage 2: Planning (Planner ↔ Plan Reviewer GAN Loop)

**Max iterations: 3.**

The planner reads `doc-audit.md` instead of `brainstorm.md`. The planner creates ONE remediation plan with phases sequenced as:
- **Early phases:** Content fixes (delete stale, fix drifted, create stubs, fix links)
- **Later phases:** Prevention tooling (doc linting, link checking, auto-gen, CI)

### 2a: Spawn Planner

- **Read** `planner.md` for the role prompt
- Spawn an **Agent** with:

```
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
```
Phase N approved after M iteration(s).
Remaining phases: [list]
```

## Stage 4: Re-Audit

After all phases are implemented and approved, re-run the doc auditor:

### 4a: Spawn Doc Auditor

- **Read** `doc-auditor.md` for the role prompt
- Spawn an **Agent** with:

```
<role_prompt>
[Contents of doc-auditor.md]
</role_prompt>

<task>
Version: $ARGUMENTS

This is a RE-AUDIT after remediation. Read the previous audit at docs/plans/$ARGUMENTS/doc-audit.md.

Re-audit all documentation against the codebase. Run all 6 phases again. Verify prior findings were addressed. Check that fixes didn't introduce new drift.

End with: DOC_AUDIT_COMPLETE
</task>
```

### 4b: Assess Results

The **orchestrator** (you) must:
1. Read the re-audit agent's output
2. Use **Write** to append a new `## Re-Audit Cycle N` section to `docs/plans/$ARGUMENTS/doc-audit.md` with the re-audit findings (preserve all previous content)
3. Check: are all DRIFT, STALE, and BROKEN LINK findings resolved?

### If all critical findings resolved: Report success

```
Pipeline complete for $ARGUMENTS.

Final verdict: DOCUMENTATION HEALTHY

[Summary: findings resolved, remaining gaps, prevention tools installed]

All fixes are committed and verified.
```

### If findings remain: Loop back to Stage 2

- Re-enter planning with the remaining findings
- **Max re-audit cycles: 2.** If findings persist after 2 full cycles, stop and surface to user. (2 cycles is sufficient because doc fixes are deterministic — drift either matches code or it doesn't. If findings persist after 2 cycles, the issue is likely a scope or design disagreement that needs human input.)
