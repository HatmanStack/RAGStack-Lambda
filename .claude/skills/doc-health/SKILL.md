---
name: doc-health
description: Audit documentation against codebase reality across 6 phases (discovery, comparison, examples, links, config, structure), then produce an audit doc for /pipeline remediation.
allowed-tools: Agent, Read, Write, Glob, Grep, Bash
---

# Documentation Health Audit

You coordinate a documentation drift audit of a codebase. The doc auditor runs as a separate agent with its own context window.

## Input

`$ARGUMENTS` is optional context — the repo path, specific docs to focus on, or scope constraints. If empty, audit the current working directory.

## Process

### Step 1: Scope the Audit

Ask the user 3-5 scoping questions, **one at a time**, preferring multiple choice:

```
What documentation should I audit?

A) All docs in the repo
B) Specific directories only (I'll tell you which)
C) README and API docs only
```

**Question priority:**
1. **Doc scope** — all docs or specific directories?
2. **Constraints** — any docs that shouldn't be touched?
3. **Language stack** — JS/TS, Python, or both? (determines auto-gen tools)
4. **CI platform** — GitHub Actions, GitLab CI, other?
5. **Prevention scope** — what tooling to add for drift prevention (markdown linting, link checking, auto-gen API docs, or none)

### Step 2: Generate Plan Identifier

Generate the directory name: `YYYY-MM-DD-docs-slug`
- Date: today's date
- Slug: short name (e.g., `docs-ragstack`, `docs-api`)
- Location: `docs/plans/YYYY-MM-DD-docs-slug/`

Create the directory.

### Step 3: Run Doc Auditor

**You** (the orchestrator) must read the role prompt file and embed its contents in the agent's prompt. Agents cannot access skill directory files.

1. **Read** `.claude/skills/pipeline/doc-auditor.md` — store contents as `AUDITOR_PROMPT`
2. Spawn an **Agent** with:

```
<role_prompt>
[Contents of doc-auditor.md]
</role_prompt>

<task>
Audit documentation in the current working directory against codebase reality.
Doc scope: [from Step 1]
Constraints: [from Step 1]
</task>
```

### Step 4: Write Audit Document

Read the auditor output. **Write** `docs/plans/YYYY-MM-DD-docs-slug/doc-audit.md`:

```markdown
---
type: doc-health
date: YYYY-MM-DD
prevention_scope: [from Step 1 — what tooling to add]
ci_platform: [from Step 1]
language_stack: [from Step 1]
---

# Documentation Audit: [repo name]

## Configuration
- **Prevention Scope:** [from Step 1]
- **CI Platform:** [from Step 1]
- **Language Stack:** [from Step 1]
- **Constraints:** [from Step 1]

## Summary
- Docs scanned: N files
- Code modules scanned: M
- Findings: X drift, Y gaps, Z stale, W broken links

## Findings
[Full auditor output organized by category:
DRIFT, GAPS, STALE, BROKEN LINKS, STALE CODE EXAMPLES, CONFIG DRIFT, STRUCTURE ISSUES]
```

### Step 5: Handoff

```
Audit complete: docs/plans/YYYY-MM-DD-docs-slug/doc-audit.md

Findings: X drift, Y gaps, Z stale, W broken links
Prevention tooling selected: [list]

To remediate, run:
/pipeline YYYY-MM-DD-docs-slug
```

## Rules

- **DO NOT** skip the scoping questions
- **DO NOT** start remediation — your only output is the audit doc
- **DO** include the full auditor output (the planner needs the detail)
- **DO** preserve file:line locations in all findings
- **DO** record the prevention scope in frontmatter — the pipeline uses this to scope fortification work
