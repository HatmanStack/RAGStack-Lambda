# Unified Audit Remediation Plan

## Overview

This plan addresses findings from three parallel audits of the RAGStack-Lambda codebase:
a health audit (22 findings across critical/high/medium/low), a 12-pillar evaluation
(scores ranging from 6-9/10), and a documentation audit (25 findings across drift, gaps,
stale, broken links, and config drift). The audits identified overlapping concerns around
a 3520-line god module, missing caching, silenced errors, broad exception handling,
and pervasive documentation drift.

Phases are sequenced subtractive-first: clean up dead code and unused artifacts before
making structural fixes, then add guardrails, and finally fix documentation. Each phase
is tagged with the implementer role responsible for it. Quick wins and CRITICAL findings
are front-loaded into the earliest possible phase.

## Prerequisites

- Python 3.13+ with `uv` for package management
- Node.js 24+
- Docker (for Lambda layer builds)
- AWS CLI and SAM CLI configured
- Access to run `npm run check` (lint + test)

## Phase Summary

| Phase | Tag | Goal | Est. Tokens |
|-------|-----|------|-------------|
| 0 | -- | Foundation: ADRs, conventions, testing strategy | ~3k |
| 1 | [HYGIENIST] | Dead code removal, dependency fixes, quick wins | ~10k |
| 2 | [IMPLEMENTER] | Critical bug fixes and performance improvements | ~18k |
| 3 | [IMPLEMENTER] | Architecture: resolver split, import cleanup, DRY | ~35k |
| 4 | [FORTIFIER] | Guardrails: type safety, exception narrowing, CI | ~15k |
| 5 | [DOC-ENGINEER] | Documentation drift fixes and prevention tooling | ~12k |

## Navigation

- [Phase-0.md](Phase-0.md) -- Foundation (ADRs, conventions, strategy)
- [Phase-1.md](Phase-1.md) -- [HYGIENIST] Cleanup and quick wins
- [Phase-2.md](Phase-2.md) -- [IMPLEMENTER] Critical fixes and performance
- [Phase-3.md](Phase-3.md) -- [IMPLEMENTER] Architectural improvements
- [Phase-4.md](Phase-4.md) -- [FORTIFIER] Guardrails and type safety
- [Phase-5.md](Phase-5.md) -- [DOC-ENGINEER] Documentation drift fixes and prevention

## Source Audit Documents

- [health-audit.md](health-audit.md) -- Tech debt findings (22 items)
- [eval.md](eval.md) -- 12-pillar evaluation scores
- [doc-audit.md](doc-audit.md) -- Documentation drift findings (25 items)
