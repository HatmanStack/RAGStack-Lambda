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

Ask scoping questions **one at a time**, preferring multiple choice. Wait for each answer before asking the next.

The doc audit runs 6 detection phases: discovery, comparison (drift/gaps/stale), code examples, link integrity, config/environment, and structure. It compares documentation claims against actual code behavior.

**Question 1** — Known pain points give the auditor a starting hypothesis:

```text
Are there parts of the documentation you already know are wrong or outdated?
Stale READMEs, broken examples, missing API docs, etc.

A) Yes (tell me which docs and what's wrong)
B) No — scan everything with fresh eyes
```

**Question 2** — Scope and constraints in one question:

```text
What documentation should I audit, and is anything off-limits?

A) All docs, no constraints
B) All docs, but skip specific files (tell me which)
C) Specific directories only (tell me which)
D) README and API docs only
```

**Question 3** — Language stack determines which auto-generation tools are available (typedoc for TS, sphinx for Python, swagger for REST APIs):

```text
What's the primary language stack?

A) JS/TS — typedoc, swagger-jsdoc available
B) Python — sphinx, mkdocstrings available
C) Both
```

**Question 4** — Prevention tooling. What automated checks to add so documentation drift becomes a CI failure instead of a periodic cleanup:

```text
What drift prevention tooling should I add after fixing the docs?

A) Markdown linting (markdownlint) + link checking (lychee) — catches formatting issues and broken links on every PR
B) Auto-generated API docs (typedoc/sphinx) — single source of truth lives in code, not prose
C) Both A and B
D) None — just fix the existing docs, no new tooling
```

### Step 2: Generate Plan Identifier

Generate the directory name: `YYYY-MM-DD-docs-slug`
- Date: today's date
- Slug: short name (e.g., `docs-ragstack`, `docs-api`)
- Location: `docs/plans/YYYY-MM-DD-docs-slug/`

Create the directory.

### Step 3: Run Doc Auditor

**You** (the orchestrator) must read the role prompt file and embed its contents in the agent's prompt. Agents cannot access skill directory files.

1. **Read** `skills/pipeline/doc-auditor.md` — store contents as `AUDITOR_PROMPT`
2. Spawn an **Agent** with:

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

### Step 4: Validate and Write Audit Document

Verify the auditor's output contains `DOC_AUDIT_COMPLETE`. If missing, the agent may have been truncated — report to the user and do NOT write doc-audit.md with partial data.

If signal present, **Write** `docs/plans/YYYY-MM-DD-docs-slug/doc-audit.md`:

```markdown
---
type: doc-health
date: YYYY-MM-DD
prevention_scope: [from Step 1 — what tooling to add]
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

### Step 5: Log to Manifest

Append an entry to `.claude/skill-runs.json` in the repo root. If the file does not exist, create it with an empty array first.

```json
{
  "skill": "doc-health",
  "date": "YYYY-MM-DD",
  "plan": "YYYY-MM-DD-docs-slug"
}
```

- Read the existing file, parse the JSON array, append the new entry, and write it back
- If the file is malformed, overwrite it with a fresh array containing only the new entry

### Step 6: Handoff

```text
Audit complete: docs/plans/YYYY-MM-DD-docs-slug/doc-audit.md

Findings: X drift, Y gaps, Z stale, W broken links
Prevention tooling selected: [list]

To remediate, run:
/pipeline YYYY-MM-DD-docs-slug
```

## Rules

- **DO NOT** skip the scoping questions
- **DO NOT** re-run the doc auditor agent after writing doc-audit.md — it runs exactly once here. Re-audit happens in `/pipeline` after all remediation is complete.
- **DO NOT** start remediation — your only output is the audit doc
- **DO** include the full auditor output (the planner needs the detail)
- **DO** preserve file:line locations in all findings
- **DO** record the prevention scope in frontmatter — the pipeline uses this to scope fortification work
