---
name: repo-health
description: Audit a codebase for technical debt across 4 vectors (architectural, structural, operational, hygiene), then produce an audit doc for /pipeline remediation.
allowed-tools: Agent, Read, Write, Glob, Grep, Bash
---

# Repo Health Audit

You coordinate a technical debt audit of a codebase. The auditor runs as a separate agent with its own context window.

## Input

`$ARGUMENTS` is optional context — the repo path, specific concerns, or scope constraints. If empty, audit the current working directory.

## Process

### Step 1: Scope the Audit

Ask the user 3-5 scoping questions, **one at a time**, preferring multiple choice:

```text
What's the primary goal for this audit?

A) General health check — find and fix everything
B) Production hardening — focus on operational/resiliency debt
C) Onboarding prep — make the codebase approachable for new devs
D) Pre-release cleanup — ship-blocking issues only
```

**Question priority:**
1. **Goal** — what matters most right now?
2. **Scope** — full repo or specific directories/modules?
3. **Existing tooling** — CI already in place? Linters configured? Pre-commit hooks?
4. **Constraints** — anything off-limits? (e.g., "don't touch the legacy auth module")

### Step 2: Generate Plan Identifier

Generate the directory name: `YYYY-MM-DD-health-slug`
- Date: today's date
- Slug: short name (e.g., `health-ragstack`, `health-api`)
- Location: `docs/plans/YYYY-MM-DD-health-slug/`

Create the directory.

### Step 3: Run Auditor

**You** (the orchestrator) must read the role prompt file and embed its contents in the agent's prompt. Agents cannot access skill directory files.

1. **Read** `.claude/skills/pipeline/health-auditor.md` — store contents as `AUDITOR_PROMPT`
2. Spawn an **Agent** with:

```xml
<role_prompt>
[Contents of health-auditor.md]
</role_prompt>

<task>
Audit the codebase in the current working directory.
Goal: [from Step 1]
Scope: [from Step 1]
Existing tooling: [from Step 1]
Constraints: [from Step 1]
</task>
```

### Step 4: Write Audit Document

Read the auditor output. **Write** `docs/plans/YYYY-MM-DD-health-slug/health-audit.md`:

```markdown
---
type: repo-health
date: YYYY-MM-DD
goal: [from Step 1]
---

# Codebase Health Audit: [repo name]

## Configuration
- **Goal:** [from Step 1]
- **Scope:** [from Step 1]
- **Existing Tooling:** [from Step 1]
- **Constraints:** [from Step 1]

## Summary
- Overall health: [CRITICAL | POOR | FAIR | GOOD | EXCELLENT]
- Total findings: X critical, Y high, Z medium, W low

## Tech Debt Ledger
[Full auditor output — prioritized findings with file:line locations]

## Quick Wins
[Low effort, high impact items from the auditor]

## Automated Scan Results
[Tool output summaries from knip/vulture, npm audit/pip-audit, etc.]
```

### Step 5: Handoff

```text
Audit complete: docs/plans/YYYY-MM-DD-health-slug/health-audit.md

Findings: X critical, Y high, Z medium, W low
Quick wins identified: N

To remediate, run:
/pipeline YYYY-MM-DD-health-slug
```

## Rules

- **DO NOT** skip the scoping questions
- **DO NOT** start remediation — your only output is the audit doc
- **DO** include the full auditor output (the planner needs the detail)
- **DO** preserve file:line locations in all findings
