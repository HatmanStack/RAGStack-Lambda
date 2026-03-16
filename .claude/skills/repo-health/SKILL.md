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

Ask scoping questions **one at a time**, preferring multiple choice. Wait for each answer before asking the next.

The health audit scans for technical debt across 4 vectors: architectural, structural, operational, and code hygiene. Findings are prioritized by severity (CRITICAL > HIGH > MEDIUM > LOW). The pipeline remediates until all CRITICAL and HIGH findings are resolved.

**Question 1** — Known pain points give the auditor a starting hypothesis instead of scanning cold:

```text
Are there parts of the codebase you already know are problematic?
Things that keep breaking, areas you dread touching, modules that slow down every PR.

A) Yes (tell me which areas and what's wrong)
B) No — scan everything with fresh eyes
```

**Question 2** — Goal determines which debt vectors the auditor emphasizes:

```text
What's the primary goal for this audit?

A) General health check — scan all 4 vectors equally
B) Production hardening — emphasize operational debt (error handling, timeouts, resource leaks, observability)
C) Onboarding prep — emphasize structural and hygiene debt (naming, dead code, documentation, test coverage)
D) Pre-release cleanup — focus on CRITICAL/HIGH items only, skip MEDIUM/LOW
```

**Question 3** — Deployment target changes what "operational debt" means. A Lambda function has different concerns than a long-running container:

```text
What's the deployment target?

A) Serverless (Lambda, Cloud Functions) — cold starts, execution limits, stateless constraints
B) Containers (ECS, Kubernetes, Docker) — resource management, health checks, graceful shutdown
C) Static hosting / SPA — build pipeline, CDN, client-side concerns
D) Monolith / traditional server — process management, connection pooling, memory leaks
E) Multiple (tell me which)
F) Not deployed yet / unsure
```

**Question 4** — Scope and constraints in one question:

```text
What should the health auditor cover, and is anything off-limits?

A) Full repo, no constraints
B) Full repo, but skip specific areas (tell me which — e.g., "don't touch the legacy auth module")
C) Specific directories only (tell me which)
```

**Question 5** — Existing tooling helps the fortifier (hardening phase) know what guardrails already exist so it doesn't duplicate work:

```text
What development tooling is already in place?

A) Full setup — linters, CI pipeline, pre-commit hooks, type checking
B) Partial (tell me what you have — e.g., "ESLint but no CI")
C) None — no linting, CI, or hooks configured
```

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
- **DO NOT** re-run the auditor agent after writing health-audit.md — it runs exactly once here. Re-audit happens in `/pipeline` after all remediation is complete.
- **DO NOT** start remediation — your only output is the audit doc
- **DO** include the full auditor output (the planner needs the detail)
- **DO** preserve file:line locations in all findings
