# Pipeline Protocol

Shared contract defining stage sequencing, signals, and communication channels for the adversarial review pipeline. All role documents reference this protocol.

## Stage Sequence

```text
+----------+     +--------------+     +-------------+     +----------+     +----------------+
| Planner  | --> | Plan Reviewer| --> | Implementer | --> | Reviewer | --> | Final Reviewer |
+----------+     +--------------+     +-------------+     +----------+     +----------------+
     ^                 |                    ^                   |                   |
     |  REVISION_      |                   |  CHANGES_         |                   |
     +--REQUIRED-------+                   +--REQUESTED--------+                   |
                                                                                   |
     ^                                     ^                                       |
     |                                     |          NO-GO                         |
     +-------------------------------------+---------------------------------------+
```

## Signals

| Signal                  | Emitted By      | Triggers                                 | Action                                                        |
|-------------------------|-----------------|------------------------------------------|---------------------------------------------------------------|
| PLAN_COMPLETE           | Planner         | Plan Reviewer                            | Review plan files and verify against codebase                 |
| REVISION_REQUIRED       | Plan Reviewer   | Planner                                  | Check feedback.md, revise plan, re-emit PLAN_COMPLETE         |
| PLAN_APPROVED           | Plan Reviewer   | Implementer                              | Begin phase implementation                                    |
| IMPLEMENTATION_COMPLETE | Implementer     | Reviewer                                 | Review code against plan                                      |
| CHANGES_REQUESTED       | Reviewer        | Implementer                              | Check feedback.md, fix issues, re-emit IMPLEMENTATION_COMPLETE|
| PHASE_APPROVED          | Reviewer        | Next phase Implementer or Final Reviewer | Start next phase or final review                              |
| GO                      | Final Reviewer  | Deploy pipeline                          | Production ready                                              |
| NO-GO                   | Final Reviewer  | Planner or Implementer                   | Check feedback.md for scope of rework                         |
| VERIFIED                | Verification Reviewer | Pipeline complete                  | All findings from intake docs confirmed addressed             |
| UNVERIFIED              | Verification Reviewer | Planner (re-entry)               | Unverified items listed, orchestrator decides next step       |
| EVAL_HIRE_COMPLETE      | Eval Hire agent | Intake orchestrator                      | Hire evaluation finished (intake only)                        |
| EVAL_STRESS_COMPLETE    | Eval Stress agent | Intake orchestrator                    | Stress evaluation finished (intake only)                      |
| EVAL_DAY2_COMPLETE      | Eval Day2 agent | Intake orchestrator                      | Day 2 evaluation finished (intake only)                       |
| AUDIT_COMPLETE          | Health Auditor  | Intake orchestrator                      | Health audit finished (intake only)                           |
| DOC_AUDIT_COMPLETE      | Doc Auditor     | Intake orchestrator                      | Doc audit finished (intake only)                              |

## Communication Channel: feedback.md

All review feedback lives in `docs/plans/<plan_id>/feedback.md`. Plan documents are **never mutated** by reviewers.

### feedback.md Structure

```markdown
# Feedback Log

## Active Feedback

### [PLAN_REVIEW | CODE_REVIEW] - Iteration N - Phase X, Task Y

> **Consider:** ...
> **Think about:** ...
> **Reflect:** ...

**Status:** OPEN

---

## Resolved Feedback

### [PLAN_REVIEW | CODE_REVIEW] - Iteration N - Phase X, Task Y

> **Consider:** ...

**Status:** RESOLVED
**Resolution:** Brief description of how it was addressed

---
```

### Rules

- **Reviewers** append new feedback under "Active Feedback" with status OPEN
- **Generators** (Planner/Implementer) move resolved items to "Resolved Feedback" with a resolution note
- Tag feedback with `PLAN_REVIEW` or `CODE_REVIEW` so the correct generator knows which items are theirs
- Reference specific files, line numbers, and test names
- Use rhetorical questions (Consider / Think about / Reflect) -- don't provide answers

## File Ownership

| File          | Created By | Edited By                                  | Purpose                           |
|---------------|------------|--------------------------------------------|------------------------------------|
| README.md     | Planner    | Planner                                    | Overview and navigation            |
| Phase-0.md    | Planner    | Planner                                    | Architecture decisions (source of truth) |
| Phase-N.md    | Planner    | Planner, Implementer (checkboxes only)     | Implementation instructions        |
| feedback.md   | Planner    | Plan Reviewer, Reviewer, Orchestrator      | All review feedback + verification results |
| eval.md       | Intake skill | Orchestrator (read only during pipeline) | Repo evaluation scores and targets         |
| health-audit.md | Intake skill | Orchestrator (read only during pipeline) | Tech debt findings                       |
| doc-audit.md  | Intake skill | Orchestrator (read only during pipeline)   | Documentation drift findings               |
