---
name: pipeline
description: Run the adversarial plan-implement-review pipeline. Spawns agents for each role with their own context windows. Use after /brainstorm, /repo-eval, /repo-health, or /doc-health has produced a starting doc.
allowed-tools: Agent, Read, Write, Glob, Grep, Bash, Edit
---

# Pipeline Orchestrator

You coordinate the adversarial development pipeline. Each role runs as a separate agent with a fresh context window. Your job is to spawn agents, read their signals, and route work accordingly.

**Read `pipeline-protocol.md` for the full signal protocol before starting.**

## Input

`$ARGUMENTS` is the plan identifier in `YYYY-MM-DD-slug` format (e.g., `2026-03-12-user-auth`). Plan files live at `docs/plans/$ARGUMENTS/`.

## Pre-Flight & Type Detection

1. **Read** `pipeline-protocol.md` to load the signal protocol
2. Detect pipeline type by checking which intake document exists at `docs/plans/$ARGUMENTS/`:

```text
+-------------------------------------------------------------------+
|                    PIPELINE TYPE ROUTING                           |
+-------------------------------------------------------------------+
|                                                                   |
|  Check which intake docs exist at docs/plans/$ARGUMENTS/:         |
|                                                                   |
|  brainstorm.md exists?    → type: feature (default flow below)    |
|  Multiple audit docs?     → type: audit (unified plan)            |
|  health-audit.md only?    → type: repo-health                     |
|  eval.md only?            → type: repo-eval                       |
|  doc-audit.md only?       → type: doc-health                      |
|  none found?              → tell user to run an intake skill      |
|                                                                   |
+-------------------------------------------------------------------+
```

Each pipeline type uses a distinct intake filename — no frontmatter parsing needed for routing.

1. **Glob** for all intake docs at `docs/plans/$ARGUMENTS/` to determine which exist
1. **If `brainstorm.md` exists**: it runs alone — continue with the feature flow stages below. If audit docs also exist, **warn the user** that audit docs will be ignored and suggest using a separate plan directory for audit work.
1. **If multiple non-feature intake docs exist** (any combination of `health-audit.md`, `eval.md`, `doc-audit.md`): **Read** `flows/audit-flow.md` and follow it. This creates ONE unified plan across all audit types. **Stop reading this file and follow the flow file.**
1. **If exactly one non-feature intake doc exists**: read the corresponding flow file and follow it. **Stop reading this file and follow the flow file.**
1. **If none found**: tell the user to run an intake skill first

## Stage 0: Pipeline State Recovery

Before starting any stage, detect prior progress to determine the correct entry point:

1. **Check for plan approval**: Read `docs/plans/$ARGUMENTS/feedback.md` (if it exists) for a `PLAN_APPROVED` signal or resolved `PLAN_REVIEW` entries with no remaining OPEN `PLAN_REVIEW` items
2. **Check for phase progress**: Look for `PHASE_APPROVED`, OPEN/resolved `CODE_REVIEW` entries, and implementation commits (see Stage 2 State Recovery)
3. **Check for final review**: Look for `GO` or `NO-GO` entries tagged `FINAL_REVIEW`

Based on findings:
- `GO` or `NO-GO` in feedback.md → pipeline already completed, report result to user and stop
- `PHASE_APPROVED` for all phases → skip to Stage 3 (Final Review)
- Any phase progress exists + `PLAN_APPROVED` → skip to Stage 2 at the correct phase (see State Recovery below)
- Plan files exist + OPEN `PLAN_REVIEW` feedback → enter Stage 1 at revision step (1a with revision instructions)
- Plan files exist + no feedback.md or no review entries → enter Stage 1 at review step (1b)
- No plan files → enter Stage 1 from the start (1a)

Report the detected state to the user before continuing.

## Stage 1: Planning (Planner ↔ Plan Reviewer GAN Loop)

**Max iterations: 3.** If not approved after 3 cycles, stop and surface the unresolved issues to the user.

### 1a: Spawn Planner

- **Read** `planner.md` to load the role prompt
- Spawn an **Agent** (subagent_type: general-purpose) with the following prompt structure:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Brainstorm document: docs/plans/$ARGUMENTS/brainstorm.md

Read the brainstorm document, explore the codebase, and create the implementation plan files at docs/plans/$ARGUMENTS/.

Remember to create feedback.md with the empty template structure.

When complete, end your response with: PLAN_COMPLETE
</task>
```

- Wait for the agent to complete
- Verify `PLAN_COMPLETE` is in the result

### 1b: Spawn Plan Reviewer

- **Read** `plan_reviewer.md` to load the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of plan_reviewer.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Plan location: docs/plans/$ARGUMENTS/

Review the implementation plan. Verify file existence with Glob. Check dependencies, actionability, and testing strategy.

If issues found: write feedback to docs/plans/$ARGUMENTS/feedback.md tagged PLAN_REVIEW, then end with: REVISION_REQUIRED
If plan is good: end with: PLAN_APPROVED
</task>
```

- Check the signal in the result:
  - `PLAN_APPROVED` → proceed to Stage 2
  - `REVISION_REQUIRED` → re-spawn Planner (1a) with revision instructions:

```xml
<role_prompt>
[Contents of planner.md]
</role_prompt>

<task>
Version: $ARGUMENTS

The Plan Reviewer has requested revisions. Read docs/plans/$ARGUMENTS/feedback.md for OPEN items tagged PLAN_REVIEW.

Address each item by revising the plan files. Move resolved feedback to the "Resolved Feedback" section with a resolution note.

When complete, end your response with: PLAN_COMPLETE
</task>
```

- Loop until `PLAN_APPROVED` or max iterations reached

### Between Stages - Report to User

After plan approval, report:
```text
Plan approved after N iteration(s).
Phases identified: [list phases found]
Starting implementation...
```

## Stage 2: Implementation (Per-Phase Implementer ↔ Reviewer GAN Loop)

**Max iterations per phase: 3.** If not approved after 3 cycles, stop and surface issues.

Identify all phases by using **Glob** for `docs/plans/$ARGUMENTS/Phase-*.md` (excluding Phase-0). Process them in sequential order.

### State Recovery (Resume Detection)

Before processing phases, determine each phase's completion state. For each Phase-N:

1. **Read** `docs/plans/$ARGUMENTS/feedback.md` and check for:
   - A `PHASE_APPROVED` entry for Phase N → phase is **done**, skip it
   - OPEN `CODE_REVIEW` items for Phase N → phase needs **review fixes**, enter at step 2a (Implementer) with revision instructions
   - Resolved `CODE_REVIEW` items for Phase N but no `PHASE_APPROVED` → phase needs **re-review**, enter at step 2b (Reviewer)
2. **Check** `git log --oneline` for commits referencing Phase N (e.g., `phase-N`, `Phase N`, `phase N`)
   - Commits exist but no feedback.md review entries → phase was **implemented but never reviewed**, enter at step 2b (Reviewer)
   - No commits and no feedback entries → phase is **not started**, enter at step 2a (Implementer)

A phase is only skip-eligible when feedback.md contains a `PHASE_APPROVED` record for it. Implementation commits alone are not sufficient.

Report the recovered state to the user before continuing:
```text
Resume state for $ARGUMENTS:
- Phase 1: [done | needs review | needs review fixes | needs implementation | not started]
- Phase 2: [...]
Continuing from Phase N...
```

### For each Phase-N

#### 2a: Spawn Implementer

- **Read** `implementer.md` to load the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of implementer.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Phase: N

Read these files in order:
1. docs/plans/$ARGUMENTS/README.md
2. docs/plans/$ARGUMENTS/Phase-0.md
3. docs/plans/$ARGUMENTS/Phase-N.md
4. docs/plans/$ARGUMENTS/feedback.md (check for OPEN CODE_REVIEW items)

Implement all tasks in Phase-N following TDD. Make atomic commits.

When complete, end your response with: IMPLEMENTATION_COMPLETE
</task>
```

#### 2b: Spawn Reviewer

- **Read** `reviewer.md` to load the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of reviewer.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Phase: N

Review the Phase N implementation:
1. Read docs/plans/$ARGUMENTS/Phase-0.md first (architecture source of truth)
2. Read docs/plans/$ARGUMENTS/Phase-N.md (the spec)
3. Verify implementation matches spec using Read, Glob, Grep
4. Run tests and build with Bash
5. Check git commits

If issues found: write feedback to docs/plans/$ARGUMENTS/feedback.md tagged CODE_REVIEW, then end with: CHANGES_REQUESTED
If implementation is good: end with: PHASE_APPROVED
</task>
```

- Check the signal:
  - `PHASE_APPROVED` → report to user, move to next phase
  - `CHANGES_REQUESTED` → re-spawn Implementer (2a) with:

```xml
<role_prompt>
[Contents of implementer.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Phase: N

The Code Reviewer has requested changes. Read docs/plans/$ARGUMENTS/feedback.md for OPEN items tagged CODE_REVIEW.

Address each item. Move resolved feedback to "Resolved Feedback" with a resolution note. Continue following TDD.

When complete, end your response with: IMPLEMENTATION_COMPLETE
</task>
```

- Loop until `PHASE_APPROVED` or max iterations reached

#### Between Phases

```text
Phase N approved after M iteration(s).
Remaining phases: [list]
```

## Stage 3: Final Review

After all phases are approved:

- **Read** `final_reviewer.md` to load the role prompt
- Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of final_reviewer.md]
</role_prompt>

<task>
Version: $ARGUMENTS
Plan location: docs/plans/$ARGUMENTS/

Conduct the final comprehensive review:
1. Run the full test suite
2. Verify spec compliance across all phases — read each Phase-N.md and verify every task has corresponding code
3. Check integration points between phases
4. Scan for security issues, dead code, and tech debt
5. Produce the Production Readiness Dashboard

If ready: end with: GO
If not ready: write feedback to docs/plans/$ARGUMENTS/feedback.md tagged FINAL_REVIEW, categorize issues as plan-level or implementation-level, then end with: NO-GO
</task>
```

- Check the signal:
  - `GO` → report success to user
  - `NO-GO` → report issues to user with the final reviewer's assessment. **Do not automatically re-enter the loop.** Let the user decide next steps.

## Completion

### On GO

```text
Pipeline complete for $ARGUMENTS.

Final verdict: GO — Production Ready

Stages completed:
- Plan: approved in N iteration(s)
- Phase 1: approved in M iteration(s)
- Phase 2: approved in M iteration(s)
- ...
- Final review: GO

All code is committed and ready for deployment.
```

### On NO-GO

```text
Pipeline stopped for $ARGUMENTS.

Final verdict: NO-GO

The final reviewer identified issues in docs/plans/$ARGUMENTS/feedback.md tagged FINAL_REVIEW.

[Summary of issues categorized as plan-level vs implementation-level]

Options:
A) Address the issues and re-run: /pipeline $ARGUMENTS
B) Review feedback manually: read docs/plans/$ARGUMENTS/feedback.md
C) Ship with caveats (if issues are minor)
```

**NO-GO Re-Entry Path:** When the user re-runs `/pipeline $ARGUMENTS` after a NO-GO, the State Recovery (Stage 0) detects the `NO-GO` in feedback.md and routes rework based on the final reviewer's categorization:
- **Plan-level issues** (architecture flaw, missing phase): Re-enter at Stage 1 (Planner) with revision instructions referencing the `FINAL_REVIEW` feedback
- **Implementation-level issues** (bug, missing test, security): Re-enter at Stage 2 at the affected phase(s), spawning the Implementer with `FINAL_REVIEW` feedback items as `CODE_REVIEW` rework
- **Mixed issues**: Plan-level first, then implementation-level

The orchestrator should update the `NO-GO` status in feedback.md to `REWORK_IN_PROGRESS` to distinguish active rework from a fresh pipeline run.

### On Max Iterations Reached

```text
Pipeline paused for $ARGUMENTS.

The [Planner ↔ Plan Reviewer | Implementer ↔ Reviewer] loop for [Phase N] did not converge after 3 iterations.

Unresolved feedback in docs/plans/$ARGUMENTS/feedback.md.

Options:
A) Review feedback and provide guidance, then re-run
B) Manually resolve and continue
```

## Rules

- **NEVER** modify source code yourself — only agents do that
- **NEVER** skip the Plan Reviewer — every plan gets reviewed
- **NEVER** skip the Code Reviewer — every implementation gets reviewed
- **NEVER** continue past a NO-GO without user input
- **DO** read each role prompt file fresh before spawning — don't cache from memory
- **DO** report progress between stages so the user knows what's happening
- **DO** include the full role prompt contents in each agent's prompt (the agent has no access to the skill directory files)
- **DO** respect the max iteration limits — surface persistent issues to the user rather than looping forever
