# Codebase Remediation to 9/10 Across All Pillars

## Overview

RAGStack-Lambda is a serverless document processing pipeline with AI chat on AWS. A code audit evaluated the codebase across four pillars -- Pragmatism, Defensiveness, Performance, and Type Rigor -- scoring 7-8/10 in each. This remediation targets 9/10 across all four pillars through three phases of work.

The work is structured as: (1) comprehensive test coverage for all untested Lambda handlers to create a safety net, (2) TypedDict introduction, mypy strict enforcement, and splitting the 1,824-line `query_kb/index.py` monolith into a package, and (3) defensive infrastructure including a DLQ replay Lambda, S3 size guards, React error boundaries, and replacing `window.alert()` with Cloudscape Flashbar notifications.

The remediation is intentionally conservative -- no logic changes, no new AWS services, no architectural rewrites. Every change is testable, reversible, and builds on existing patterns.

## Prerequisites

- Python 3.13+ (use `uv` for all Python package management, never pip directly)
- Node.js 24+ (managed via nvm)
- AWS CLI + SAM CLI configured
- Docker (required for Lambda layer builds)
- Existing dependencies: `uv pip install -r requirements.txt`
- Frontend dependencies: `cd src/ui && npm ci` and `cd src/ragstack-chat && npm ci`

## Commit Message Guidelines

- Use conventional commits format: `type(scope): description`
- Do NOT include `Co-Authored-By` or `Generated-By` attribution lines
- Do NOT include emoji in commit messages

## Python Style

- Python 3.13 syntax: use `str | None` not `Optional[str]`, `dict[str, Any]` not `Dict[str, Any]`
- Line length: 100 characters (configured in pyproject.toml)
- Linting: `uv run ruff check .` and `uv run ruff format .`

## Phase Summary

| Phase | Goal | Estimated Tokens | File |
|:------|:-----|:----------------|:-----|
| 0 | Foundation: architecture decisions, patterns, testing strategy | ~5,000 | [Phase-0.md](Phase-0.md) |
| 1 | Test coverage for all untested Lambda handlers + logging_utils | ~45,000 | [Phase-1.md](Phase-1.md) |
| 2 | TypedDicts, mypy strict, query_kb package split | ~45,000 | [Phase-2.md](Phase-2.md) |
| 3 | DLQ replay Lambda, S3 size guard, error boundaries, Flashbar | ~40,000 | [Phase-3.md](Phase-3.md) |

## Navigation

- [Phase-0.md](Phase-0.md) -- Foundation (read first, applies to all phases)
- [Phase-1.md](Phase-1.md) -- Test Coverage Safety Net
- [Phase-2.md](Phase-2.md) -- Type Rigor and query_kb Refactor
- [Phase-3.md](Phase-3.md) -- Defensive Infrastructure
- [feedback.md](feedback.md) -- Feedback channel for plan review
- [brainstorm.md](brainstorm.md) -- Original brainstorm document
