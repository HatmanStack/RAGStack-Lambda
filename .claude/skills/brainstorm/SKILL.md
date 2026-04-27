---
name: brainstorm
description: Interactively explore a codebase and refine a feature idea into a structured design spec through clarifying questions. Use when starting a new feature.
---

# Feature Brainstorm

You are helping the user refine a feature idea into a complete design spec through structured exploration and questioning.

## Input

The user will provide a feature idea as `$ARGUMENTS`. This may be a description, a pointer to a document, or a rough concept.

## Process

### Step 1: Understand the Feature Idea

Read the user's feature description carefully. If they point to a document, read it.

### Step 2: Explore Relevant Codebase

**Focus your exploration on areas relevant to the feature idea.** Do not survey the entire codebase.

- Use **Glob** to find files in areas the feature will touch
- Use **Grep** to find existing patterns, utilities, or conventions
- Use **Read** to understand key files, config, and project structure
- Check `package.json`, `requirements.txt`, or equivalent for dependencies and scripts
- Look at recent git history for active areas: `git log --oneline -20`

Build a mental model of: tech stack, project structure, existing patterns the feature should follow, and integration points.

### Step 3: Ask Clarifying Questions

Ask questions **one at a time**. Aim for **5-15 questions** total, prioritizing high-impact scope decisions.

**Prefer multiple choice**, but open-ended is fine when the option space is too large:

```text
The codebase uses DynamoDB for storage. For this feature's data, should we:

A) Add tables to the existing DynamoDB setup
B) Use a different storage approach (e.g., S3 for documents)
C) Both — DynamoDB for metadata, S3 for content
```

**Question priority order:**
1. **Scope** — What's in, what's out? MVP vs full vision?
2. **Architecture** — How does this integrate with existing code?
3. **Data model** — What entities, relationships, storage?
4. **User-facing behavior** — Inputs, outputs, error cases?
5. **Non-functional** — Performance, security, deployment constraints?

**Rules:**
- One question per message
- Wait for the user's answer before asking the next question
- Reference specific files/patterns you found during exploration to ground questions in reality
- If a question has an obvious answer based on existing codebase patterns, state your assumption and ask for confirmation instead
- Track which questions you've asked and what's been decided

### Step 4: Confirm Scope

After gathering enough context (you'll know — the remaining questions are minor details the planner can handle), summarize what you've learned and confirm with the user:

```text
I think I have a clear picture. Here's what I understand:

- [Key decision 1]
- [Key decision 2]
- ...

Anything I'm missing, or should we proceed to creating the design spec?
```

### Step 5: Write Brainstorm Document

Generate the plan directory name using **date + feature slug** format:
- Date: today's date as `YYYY-MM-DD`
- Slug: short, lowercase, hyphenated feature name derived from the Q&A (e.g., `user-auth`, `search-api`, `billing-webhooks`)
- Result: `docs/plans/YYYY-MM-DD-feature-slug/`
- If a directory with that name already exists (same feature, same day), append `-2`, `-3`, etc.

Create `docs/plans/YYYY-MM-DD-feature-slug/brainstorm.md` using **Write**:

```markdown
# Feature: [Name]

## Overview
[What we're building — 2-3 paragraphs covering the full picture]

## Decisions
[Numbered list of every decision made during Q&A, with brief rationale]
- 1. Auth approach: JWT — aligns with existing middleware in src/auth/
- 2. Storage: DynamoDB — project already uses it, no reason to add complexity
- ...

## Scope: In
[Bulleted list of what IS included]

## Scope: Out
[Bulleted list of what is explicitly EXCLUDED — important for the planner]

## Open Questions
[Anything unresolved that the Planner will need to decide or ask about]
[If none, state "None — all scope decisions resolved"]

## Relevant Codebase Context
[Key files, patterns, and conventions discovered during exploration]
- `src/auth/middleware.ts` — existing auth pattern to follow
- `lib/dynamodb.ts` — shared DynamoDB client and table utilities
- Test pattern: Jest with mocks in `__mocks__/` directories
- ...

## Technical Constraints
[Any limitations, dependencies, or deployment considerations discovered]
```

### Step 6: Log to Manifest

Append an entry to `.claude/skill-runs.json` in the repo root. If the file does not exist, create it with an empty array first.

```json
{
  "skill": "brainstorm",
  "date": "YYYY-MM-DD",
  "plan": "YYYY-MM-DD-feature-slug"
}
```

- Read the existing file, parse the JSON array, append the new entry, and write it back
- If the file is malformed, overwrite it with a fresh array containing only the new entry

### Step 7: Handoff

After writing the brainstorm document:

```text
Brainstorm complete: docs/plans/YYYY-MM-DD-feature-slug/brainstorm.md

To start the automated build pipeline, run:
/pipeline YYYY-MM-DD-feature-slug
```

## Rules

- **DO NOT** skip the Q&A and jump to writing the brainstorm doc
- **DO NOT** ask more than one question per message
- **DO NOT** explore unrelated parts of the codebase
- **DO NOT** start planning or implementation — your only output is the brainstorm doc
- **DO** ground every question in what you found in the codebase
- **DO** state assumptions and ask for confirmation when the answer seems obvious
