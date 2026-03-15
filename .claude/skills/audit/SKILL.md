---
name: audit
description: Run one or more codebase audits (evaluation, health, documentation) sequentially, producing intake docs for a single /pipeline run.
allowed-tools: Agent, Read, Write, Glob, Grep, Bash
---

# Audit

You coordinate one or more codebase audits. All scoping questions are asked upfront in a single batch. Then all agents run without further user interaction, producing intake docs for a single `/pipeline` command.

## Input

`$ARGUMENTS` is optional context — specific concerns, repo path, or which audits to run.

## Process

### Step 1: Collect All Configuration Upfront

Present **one message** with all questions. The user answers everything at once, then you execute.

```text
Which audits should I run?

A) All three (health → eval → docs)
B) Code evaluation — 12-pillar scoring across 3 lenses
C) Technical debt — audit across 4 vectors
D) Documentation — drift detection across 6 phases

---

For the audits you selected, answer the relevant sections below.
Skip sections for audits you didn't select.

### Code Evaluation (if B or A)
1. Role level: [Junior | Mid | Senior | Staff+]
2. Focus areas: [any specific concerns? or "none"]
3. Context: [side project | production app | interview take-home]
4. Exclusions: [directories/files to skip, or "none"]
5. Pillar overrides: [any pillars to accept below 9? e.g., "Creativity: 7", or "none"]

### Technical Debt (if C or A)
1. Goal: [general health check | production hardening | onboarding prep | pre-release cleanup]
2. Scope: [full repo | specific directories]
3. Existing tooling: [linters, CI, pre-commit hooks already in place? or "none"]
4. Constraints: [anything off-limits? or "none"]

### Documentation (if D or A)
1. Doc scope: [all docs | specific directories | README and API docs only]
2. Constraints: [any docs that shouldn't be touched? or "none"]
3. Language stack: [JS/TS | Python | both]
4. CI platform: [GitHub Actions | GitLab CI | other | none]
5. Prevention tooling: [markdown linting + link checking | auto-gen API docs | both | none]
```

If `$ARGUMENTS` already provides answers (e.g., "/audit all, senior, production app, no exclusions"), extract what you can and only ask for missing information.

### Step 2: Generate Plan Identifier

Generate the directory name: `YYYY-MM-DD-audit-slug`
- Date: today's date
- Slug: short name for the repo (e.g., `audit-ragstack`, `audit-my-app`)
- Location: `docs/plans/YYYY-MM-DD-audit-slug/`

Create the directory.

### Step 3: Read Role Prompts

Before spawning agents, read all required role prompt files. Only read prompts for selected audits.

- **If health selected:** Read `.claude/skills/pipeline/health-auditor.md`
- **If eval selected:** Read `.claude/skills/pipeline/eval-hire.md`, `.claude/skills/pipeline/eval-stress.md`, `.claude/skills/pipeline/eval-day2.md`
- **If docs selected:** Read `.claude/skills/pipeline/doc-auditor.md`

### Step 4: Spawn All Agents in Parallel

All auditor/evaluator agents are read-only — they explore the codebase but don't modify it. Spawn all selected agents in a single parallel batch (up to 5 agents for "all"):

```text
+-------------------------------------------------------------------+
|                    PARALLEL AGENT SPAWN                            |
+-------------------------------------------------------------------+
|                                                                   |
|  health auditor ─┐                                                |
|  eval hire ──────┤                                                |
|  eval stress ────┤  all agents run simultaneously                 |
|  eval day2 ──────┤                                                |
|  doc auditor ────┘                                                |
|                  ↓                                                |
|  orchestrator collects all responses, writes intake docs          |
|                                                                   |
+-------------------------------------------------------------------+
```

**Agent 1: Health Auditor** (if health selected)
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

**Agent 2: Eval — The Pragmatist** (if eval selected)
```xml
<role_prompt>
[Contents of eval-hire.md]
</role_prompt>

<task>
Evaluate the codebase in the current working directory.
Role level: [from Step 1]
Focus areas: [from Step 1]
Exclusions: [from Step 1]
</task>
```

**Agent 3: Eval — The Oncall Engineer** (if eval selected)
```xml
<role_prompt>
[Contents of eval-stress.md]
</role_prompt>

<task>
Evaluate the codebase in the current working directory.
Role level: [from Step 1]
Focus areas: [from Step 1]
Exclusions: [from Step 1]
</task>
```

**Agent 4: Eval — The Team Lead** (if eval selected)
```xml
<role_prompt>
[Contents of eval-day2.md]
</role_prompt>

<task>
Evaluate the codebase in the current working directory.
Role level: [from Step 1]
Focus areas: [from Step 1]
Exclusions: [from Step 1]
</task>
```

**Agent 5: Doc Auditor** (if docs selected)
```xml
<role_prompt>
[Contents of doc-auditor.md]
</role_prompt>

<task>
Audit documentation in the current working directory against codebase reality.
Doc scope: [from Step 1]
Constraints: [from Step 1]
</task>
```

### Step 5: Collect Results and Write Intake Docs

After all agents complete, the **orchestrator** (you) reads each agent's output and writes the intake docs:

- **Health:** Write `docs/plans/YYYY-MM-DD-audit-slug/health-audit.md` with `type: repo-health` in frontmatter
- **Eval:** Combine all 3 evaluator outputs into `docs/plans/YYYY-MM-DD-audit-slug/eval.md` with `type: repo-eval` and `pillar_overrides` in frontmatter
- **Docs:** Write `docs/plans/YYYY-MM-DD-audit-slug/doc-audit.md` with `type: doc-health` in frontmatter

See the individual intake skill SKILL.md files (repo-health, repo-eval, doc-health) for the exact output templates.

### Step 6: Handoff

```text
Audit complete: docs/plans/YYYY-MM-DD-audit-slug/

Intake docs produced:
- [health-audit.md — X critical, Y high, Z medium, W low]
- [eval.md — N/12 pillars at target]
- [doc-audit.md — X drift, Y gaps, Z stale, W broken links]

To remediate, run:
/pipeline YYYY-MM-DD-audit-slug

The pipeline will run flows in order: health → eval → docs
```

## Rules

- **DO NOT** ask questions one at a time — present all questions in a single message
- **DO NOT** prompt the user again after they answer — run all agents autonomously
- **DO NOT** start remediation — your only output is the intake docs
- **DO** embed role prompt contents in agent prompts (agents cannot access skill directory files)
- **DO** produce all intake docs in the same plan directory
- **DO** report results after each audit completes
